import json
import logging
import os

import boto3
from boto3.dynamodb.types import TypeDeserializer
from cluster import Cluster
from target import InputTarget, TargetLocation, Tenant, logger

TARGETS_TABLE = os.getenv("TARGETS_TABLE", None)

dynamodb = boto3.client("dynamodb")
dynamodb_resource = boto3.resource("dynamodb")
table = dynamodb_resource.Table(TARGETS_TABLE)

deserializer = TypeDeserializer()


class DynamodbTargets(TargetLocation):
    """
    Fetch the target locations from the DynamoDB table.
    """

    def __init__(
        self,
    ):
        logger.info(f"Fetching TargetLocations from DynamoDB Table - {TARGETS_TABLE}")

        if TARGETS_TABLE is None:
            raise Exception("TARGETS_TABLE environment variable not set")

    @staticmethod
    def get_input_accounts(eks_clusters: [Cluster]) -> (set[str], set[str]):
        account_set: set[str] = set()
        region_set: set[str] = set()

        for input_cluster in eks_clusters:
            account_set.add(input_cluster.get("AccountId"))
            region_set.add(input_cluster.get("Region"))

        return account_set, region_set

    def get_locations_using_clusters(self, eks_clusters: [Cluster]) -> []:
        """
        Get the target locations from the DynamoDB table.

        Returns:
            []: List of target locations
            eks_clusters: Array of input EKS clusters
        """

        locations = []

        scan_kwargs = {
            "TableName": TARGETS_TABLE,
            "Select": "SPECIFIC_ATTRIBUTES",
            "ProjectionExpression": "Account, #target_region, ExecutionRoleName",
            "ExpressionAttributeNames": {"#target_region": "Region"},
        }

        try:
            done = False
            start_key = None
            while not done:
                if start_key:
                    scan_kwargs["ExclusiveStartKey"] = start_key
                response = dynamodb.scan(**scan_kwargs)
                locations.extend(response.get("Items", []))
                start_key = response.get("LastEvaluatedKey", None)
                done = start_key is None

            if len(locations) == 0:
                logging.warning("No targets present")
                return []

        except Exception as e:
            logger.error(f"Error while retrieving targets: {e}")
            raise e

        input_accounts, input_regions = self.get_input_accounts(eks_clusters)

        targets_locations = []
        for location in locations:
            deserialized_document = {
                k: deserializer.deserialize(v) for k, v in location.items()
            }

            if len(input_accounts) > 0 and len(input_regions) > 0:
                target: InputTarget = self.extract_target_from_input(
                    deserialized_document
                )
                if (
                    target.get("Account") in input_accounts
                    and target.get("Region") in input_regions
                ):
                    targets_locations.append(self.get_target(deserialized_document))
            else:
                targets_locations.append(self.get_target(deserialized_document))

        return targets_locations

    def extract_target_from_input(self, item: dict) -> InputTarget:
        """
        Convert a dynamodb item to an InputTarget

        Args:
            item: DynamoDB item to extract

        Returns:
            InputTarget
        """

        input_target_str = json.dumps(item)
        input_target: InputTarget = json.loads(input_target_str)
        logger.debug(f"Input Target Location: {input_target}")

        return input_target

    @staticmethod
    def onboard_tenants(tenants: [Tenant]) -> [Tenant]:

        try:
            inserted_items: [Tenant] = []
            with table.batch_writer() as writer:
                for tenant in tenants:
                    writer.put_item(
                        Item={
                            "Account": tenant.get("AccountId"),
                            "Region": tenant.get("Region"),
                            "ExecutionRoleName": tenant.get("ExecutionRoleName"),
                        }
                    )
                    inserted_items.append(tenant)
            return inserted_items

        except Exception as e:
            logger.error(f"Error while batch inserting tenants: {e}")
            raise e

    def onboard_tenant(self, tenant: Tenant) -> [Tenant]:
        return self.onboard_tenants([tenant])
