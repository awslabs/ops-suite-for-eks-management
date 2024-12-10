import os
from datetime import datetime

import boto3
from athena import ClusterRepository
from aws_lambda_powertools import Tracer
from aws_lambda_powertools.event_handler import (
    APIGatewayRestResolver,
    Response,
    content_types,
)
from aws_lambda_powertools.event_handler.openapi.exceptions import (
    RequestValidationError,
)
from aws_lambda_powertools.event_handler.openapi.params import Path, Query
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.shared.types import Annotated
from aws_lambda_powertools.utilities.typing import LambdaContext
from dynamodb import DynamodbTargets
from models import *
from utils import *

tracer = Tracer()
logger = Logger()
lambda_client = boto3.client("lambda")
ssm_client = boto3.client("ssm")
s3_client = boto3.client("s3")
sts_client = boto3.client("sts")

# Environment Variables
SUMMARY_AUTOMATION_LAMBDA = os.getenv("SUMMARY_AUTOMATION_LAMBDA")
BACKUP_AUTOMATION_LAMBDA = os.getenv("BACKUP_AUTOMATION_LAMBDA")
UPGRADE_AUTOMATION_LAMBDA = os.getenv("UPGRADE_AUTOMATION_LAMBDA")
LAMBDA_INVOCATION_TYPE = os.getenv("LAMBDA_INVOCATION_TYPE")
LAMBDA_LOG_TYPE = os.getenv("LAMBDA_LOG_TYPE", "Tail")
S3_BUCKET = os.getenv("S3_BUCKET")
OPEN_SPEC_API_LOCATION = os.getenv("OPEN_SPEC_API_LOCATION")

# API Resolver
app = APIGatewayRestResolver(enable_validation=True)
dynamodb_target: DynamodbTargets = DynamodbTargets()

# Constants
REPORT_DATE_FORMAT = "%Y-%m-%d"


@app.exception_handler(RequestValidationError)
def handle_validation_error(ex: RequestValidationError):
    logger.error(
        "Request failed validation", path=app.current_event.path, errors=ex.errors()
    )

    return Response(
        status_code=422,
        content_type=content_types.APPLICATION_JSON,
        body={
            "StatusCode": 422,
            "Response": {"Error": {"Message": f"Bad Request. {ex.errors()}"}},
        },
    )


@app.get("/clusters")
@tracer.capture_method
def get_clusters_info(
    account_id: Annotated[Optional[str], Query(alias="AccountId")] = None,
    region: Annotated[Optional[str], Query(alias="Region")] = None,
    cluster_name: Annotated[Optional[str], Query(alias="ClusterName")] = None,
    report_date: Annotated[Optional[str], Query(alias="ReportDate")] = None,
    information: Annotated[
        Optional[str], Query(alias="Information", examples=valid_information_types())
    ] = "Metadata",
    information_relative_date: Annotated[
        Optional[bool], Query(alias="InformationRelativeDate")
    ] = False,
    query_cache: Annotated[Optional[bool], Query(alias="QueryCache")] = True,
):
    logger.info(
        f"account_id: {account_id}, region: {region}, cluster_name: {cluster_name}, "
        f"information: {information}, report_date: {report_date}"
    )

    if report_date is not None and information_relative_date:
        return Response(
            status_code=422,
            content_type=content_types.APPLICATION_JSON,
            body={
                "StatusCode": 422,
                "Response": {
                    "Error": {
                        "Message": f"ReportDate and InformationRelativeDate are mutually exclusive."
                    }
                },
            },
        )

    if report_date is not None and not datetime.strptime(
        report_date, REPORT_DATE_FORMAT
    ):
        return Response(
            status_code=422,
            content_type=content_types.APPLICATION_JSON,
            body={
                "StatusCode": 422,
                "Response": {
                    "Error": {"Message": f"Report date should be YYYY-mm-dd format."}
                },
            },
        )

    if information not in valid_information_types():
        return Response(
            status_code=422,
            content_type=content_types.APPLICATION_JSON,
            body={
                "StatusCode": 422,
                "Response": {
                    "Error": {
                        "Message": f"Information type {information} not supported."
                    }
                },
            },
        )

    repository = ClusterRepository(
        account_id=account_id,
        region=region,
        cluster_name=cluster_name,
        information=information,
        query_cache=query_cache,
        report_date=report_date,
        relative_date=information_relative_date,
    )

    try:
        clusters: [] = repository.get_clusters()

        response = {
            "StatusCode": 200,
            "Request": {
                "AccountId": account_id,
                "Region": region,
                "ClusterName": cluster_name,
                "Information": information,
                "ReportDate": repository.latest_date,
                "InformationRelativeDate": information_relative_date,
                "QueryCache": query_cache,
            },
            "Response": {"Clusters": clusters},
        }

    except Exception as e:
        logger.error(f"Failed to fetch cluster information: {e}")
        response = {"StatusCode": 500, "Response": {"Error": dict(Message=f"{str(e)}")}}
    return Response(
        status_code=response["StatusCode"],
        content_type=content_types.APPLICATION_JSON,
        body=response,
    )


@app.get("/clusters/<execution_id>")
@tracer.capture_method
def get_execution_status(execution_id: Annotated[str, Path()]):
    logger.info(f"Fetching SSM Automation status for execution {execution_id}")
    automation_status: dict = get_ssm_automation_status(ssm_client, execution_id)
    return Response(
        status_code=200,
        content_type=content_types.APPLICATION_JSON,
        body=automation_status,
    )


@app.post("/clusters/summary")
@tracer.capture_method
def start_summary(clusters: Optional[SummaryRequest] = None):
    logger.info(f"Starting summary automation for clusters {clusters}")
    payload: dict = {}

    if clusters:
        payload = clusters.dict()

    lambda_response: dict = invoke_lambda_function(
        lambda_client,
        SUMMARY_AUTOMATION_LAMBDA,
        payload,
        LAMBDA_INVOCATION_TYPE,
        LAMBDA_LOG_TYPE,
    )

    return Response(
        status_code=202,
        content_type=content_types.APPLICATION_JSON,
        body=lambda_response,
    )


@app.patch("/clusters/upgrade")
@tracer.capture_method
def upgrade_clusters(clusters: UpgradeRequest):
    logger.info(f"Upgrading {clusters}")
    payload: dict = clusters.dict()
    lambda_response: dict = invoke_lambda_function(
        lambda_client,
        UPGRADE_AUTOMATION_LAMBDA,
        payload,
        LAMBDA_INVOCATION_TYPE,
        LAMBDA_LOG_TYPE,
    )
    return Response(
        status_code=202,
        content_type=content_types.APPLICATION_JSON,
        body=lambda_response,
    )


@app.post("/clusters/backup")
@tracer.capture_method
def create_backups(clusters: BackupRequest):
    logger.info(f"Creating backups for {clusters}")
    payload: dict = clusters.dict()
    lambda_response: dict = invoke_lambda_function(
        lambda_client,
        BACKUP_AUTOMATION_LAMBDA,
        payload,
        LAMBDA_INVOCATION_TYPE,
        LAMBDA_LOG_TYPE,
    )
    return Response(
        status_code=202,
        content_type=content_types.APPLICATION_JSON,
        body=lambda_response,
    )


@app.post("/clusters/restore")
@tracer.capture_method
def create_restores(clusters: RestoreRequest):
    logger.info(f"Creating restores for {clusters}")
    payload: dict = clusters.dict()
    lambda_response: dict = invoke_lambda_function(
        lambda_client,
        BACKUP_AUTOMATION_LAMBDA,
        payload,
        LAMBDA_INVOCATION_TYPE,
        LAMBDA_LOG_TYPE,
    )
    return Response(
        status_code=202,
        content_type=content_types.APPLICATION_JSON,
        body=lambda_response,
    )


@app.put("/tenants/onboard")
@tracer.capture_method
def onboard_tenants_in_batch(request: TenantRequest):
    logger.info(f"Onboarding {request}")
    tenants_dict_list: [] = []
    tenants: [Tenant] = request.Tenants
    for tenant in tenants:
        tenants_dict_list.append(tenant.dict())

    try:
        assume_roles(sts_client, tenants_dict_list)
    except Exception as e:
        logger.error(f"Failed to assume roles: {e}")
        return {
            "StatusCode": 500,
            "Response": {
                "Error": {
                    "Message": f"Failed to assume roles: {e}. Make sure you have configured the tenant accounts"
                }
            },
        }

    try:
        db_response = dynamodb_target.onboard_tenants(tenants_dict_list)
        logger.debug(f"Records inserted - {db_response}")
    except ClientError as e:
        logger.error(f"Failed to insert records into dynamodb: {e}")
        return {
            "StatusCode": 500,
            "Response": {
                "Error": {"Message": f"Failed to insert records into dynamodb"}
            },
        }

    try:
        bucket_policy_response = update_bucket_policy(
            s3_client, S3_BUCKET, tenants_dict_list
        )
        logger.debug(f"Policy updated - {bucket_policy_response}")
    except ClientError as e:
        logger.error(f"Failed to update s3 bucket policy: {e}")
        return {
            "StatusCode": 500,
            "Response": {"Error": {"Message": f"Failed to update s3 bucket policy"}},
        }

    response: dict = {
        "StatusCode": 200,
        "Request": tenants,
        "Response": {
            "InsertedRecords": db_response,
            "PutBucketPolicy": bucket_policy_response,
        },
    }
    return Response(
        status_code=200, content_type=content_types.APPLICATION_JSON, body=response
    )


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
