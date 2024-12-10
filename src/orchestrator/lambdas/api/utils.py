import json

from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

logger = Logger()

BUCKET_ACCESS_SID: str = "CrossAccountBucketAccess"
OBJECT_ACCESS_SID: str = "CrossAccountObjectAccess"


def invoke_lambda_function(
    lambda_client,
    function_name: str,
    payload: dict,
    invocation_type: str,
    log_type: str,
) -> dict:
    logger.info(f"Invoking {function_name} with payload: {payload}")
    try:
        lambda_response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType=invocation_type,
            LogType=log_type,
            Payload=json.dumps(payload),
        )

        response = json.loads(lambda_response["Payload"].read())

    except ClientError as e:
        logger.error(f"Failed to invoke lambda function - {function_name}: {e}")
        response = {"StatusCode": 500, "Response": {"Error": {"Message": f"{str(e)}"}}}

    logger.info(f"Response from the lambda - {response}")
    return response


def get_ssm_automation_status(ssm_client, execution_id: str) -> dict:
    logger.info(f"Fetching automation status for {execution_id}")
    try:
        client_response = ssm_client.get_automation_execution(
            AutomationExecutionId=execution_id
        )

        logger.debug(f"SSM Automation Execution response: {client_response}")

        if 200 == client_response["ResponseMetadata"]["HTTPStatusCode"]:

            automation_execution: dict = client_response["AutomationExecution"]

            steps = []
            for step_exec in automation_execution["StepExecutions"]:
                step: dict = {
                    "Name": step_exec["StepName"],
                    "Status": step_exec["StepStatus"],
                    "StepExecutionId": step_exec["StepExecutionId"],
                }

                steps.append(step)

            response = {
                "StatusCode": 200,
                "Response": {
                    "ExecutionId": execution_id,
                    "DocumentName": automation_execution.get("DocumentName"),
                    "Status": automation_execution.get("AutomationExecutionStatus"),
                    "StartTime": automation_execution.get("ExecutionStartTime"),
                    "EndTime": automation_execution.get("ExecutionEndTime", None),
                    "Progress": automation_execution.get("ProgressCounters"),
                    "TargetLocations": automation_execution.get("TargetLocations"),
                    "StepExecutions": steps,
                },
            }

        else:
            response = {
                "StatusCode": 500,
                "Response": {
                    "Error": {
                        "Message": f"Failed to fetch SSM execution status for {execution_id}"
                    }
                },
            }

    except ClientError as e:
        logger.error(
            f"Failed to get status of automation execution - {execution_id}: {e}"
        )
        response = {"StatusCode": 500, "Response": {"Error": {"Message": f"{str(e)}"}}}
    return response


def valid_information_types() -> []:
    return [
        "Metadata",
        "DeprecatedAPIs",
        "Addons",
        "UnhealthyPods",
        "SingletonResources",
        "CertificateSigningRequests",
        "PodSecurityPolicies",
        "Backup",
        "Restore",
        "Upgrade",
        "AddonUpgrades",
        "NodeGroupUpgrades",
        "PostUpgrade",
    ]


def get_existing_bucket_policy(s3_client, bucket_name: str) -> dict:
    try:
        response = s3_client.get_bucket_policy(Bucket=bucket_name)
        return json.loads(response["Policy"])
    except ClientError as e:
        logger.error(f"Failed to get bucket policy - {bucket_name}: {e}")
        raise


def get_existing_bucket_policy_principals(statements: []):
    if statements and len(statements) > 0:
        for statement in statements:
            if statement.get("Sid") == BUCKET_ACCESS_SID:
                existing_principal = statement.get("Principal", {})
                return existing_principal.get("AWS")


def get_existing_policy_accounts(statements: []) -> set[str]:
    accounts: set[str] = set()
    existing_policy_accounts = get_existing_bucket_policy_principals(statements)
    logger.info(f"existing_policy_accounts: {existing_policy_accounts}")

    if existing_policy_accounts:
        if (
            isinstance(existing_policy_accounts, list)
            and len(existing_policy_accounts) > 0
        ):
            for existing_policy_account in existing_policy_accounts:
                accounts.add(existing_policy_account)
        else:
            accounts.add(existing_policy_accounts)

    return accounts


def get_bucket_policy_principals(
    existing_policy: dict, tenant_accounts: [str]
) -> list[str]:
    principals: set[str] = set()
    if existing_policy:
        statements: [] = existing_policy.get("Statement", [])
        principal_accounts: set[str] = get_existing_policy_accounts(statements)
        principals.update(principal_accounts)

    for account in tenant_accounts:
        principals.add(f"arn:aws:iam::{account}:root")

    return list(principals)


def put_bucket_policy(s3_client, bucket_name: str, policy: dict):
    try:
        response = s3_client.put_bucket_policy(
            Bucket=bucket_name, Policy=json.dumps(policy)
        )

        logger.info(f"Updated bucket policy - {response}")
    except ClientError as e:
        logger.error(f"Failed to update bucket policy - {bucket_name}: {e}")
        raise e


def update_bucket_policy(s3_client, bucket: str, tenants: []):
    try:
        tenant_accounts = map(lambda t: t["AccountId"], tenants)
        existing_policy: dict = get_existing_bucket_policy(s3_client, bucket)
        principals: list[str] = get_bucket_policy_principals(
            existing_policy, tenant_accounts
        )

        updated_policy: dict = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": BUCKET_ACCESS_SID,
                    "Effect": "Allow",
                    "Principal": {"AWS": principals},
                    "Action": "s3:ListBucket",
                    "Resource": f"arn:aws:s3:::{bucket}",
                },
                {
                    "Sid": OBJECT_ACCESS_SID,
                    "Effect": "Allow",
                    "Principal": {"AWS": principals},
                    "Action": ["s3:GetObject", "s3:PutObject", "s3:PutObjectAcl"],
                    "Resource": f"arn:aws:s3:::{bucket}/*",
                },
            ],
        }

        put_bucket_policy(s3_client, bucket, updated_policy)
        logger.info(f"Updated bucket policy")
        return updated_policy

    except Exception as e:
        raise e


def assume_roles(sts_client, tenants: []):
    count: int = 0
    for tenant in tenants:
        role = tenant["ExecutionRoleName"]
        account_id = tenant["AccountId"]
        count = count + 1
        try:
            sts_client.assume_role(
                RoleArn=f"arn:aws:iam::{account_id}:role/{role}",
                RoleSessionName=f"{role}-{count}",
                DurationSeconds=900,
                ExternalId=f"{role}-{count}",
            )
            logger.info(f"Assumed role - {role}")
        except Exception as e:
            logger.error(f"Failed to assume role {role} - {e}")
            raise e
