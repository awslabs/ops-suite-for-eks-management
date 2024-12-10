import argparse
import csv
import logging
import os
import sys

import boto3
from botocore.exceptions import ClientError

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("-p", "--profile", help="aws profile name")
arg_parser.add_argument("-r", "--region", help="aws region")
arg_parser.add_argument("-t", "--table", help="dynamodb table name")
arg_parser.add_argument("-a", "--accounts", help="Tenant account id")
arg_parser.add_argument("-o", "--orgs", help="Orchestrator Account id")

# Constants
DEFAULT_TARGET_SSM_EXECUTION_ROLE = "EKSManagement-SSMAutomationExecutionRole"


class DynamoDbOps:
    region: str = None
    aws_profile: str = None
    table_name: str = None
    org_id: str = None
    account_id: str = None

    def __init__(self):
        self.logging = logging.getLogger("DynamoDbOps")
        self.logging.setLevel(logging.INFO)
        self.logging.addHandler(logging.StreamHandler(sys.stdout))

        self.parse_arguments()

        if self.aws_profile is None:
            self.aws_profile = "default"

        if self.account_id is None and self.org_id is None:
            self.logging.error("No target accounts or organisational unit ids passed.")
            sys.exit(1)

        session = boto3.Session(profile_name=self.aws_profile, region_name=self.region)
        self.dynamodb_resource = session.resource("dynamodb")

        self.logging.info(f"Using {self.aws_profile} aws profile")

    def insert_items(self):
        try:
            table = self.get_table_resource()
            items = self.get_items_to_insert()
            with table.batch_writer() as writer:
                for item in items:
                    writer.put_item(Item=item)
        except ClientError as e:
            self.logging.error(
                f"Exception while inserting items into {self.table_name}: {e}"
            )
            sys.exit(1)

    def get_table_resource(self):
        try:
            return self.dynamodb_resource.Table(self.table_name)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                self.logging.error(f"{self.table_name} Table not found")
            else:
                self.logging.error(f"Exception while getting dynamodb resource: {e}")
            sys.exit(1)

    def parse_arguments(self):
        arguments = arg_parser.parse_args()
        self.aws_profile = arguments.profile
        self.region = arguments.region
        self.table_name = arguments.table
        self.account_id = arguments.accounts
        self.org_id = arguments.orgs

    def get_items_to_insert(self) -> list:
        items_list = []

        # if self.account_file is not None and os.path.isfile(self.account_file):
        #     with open(self.account_file, mode='r') as file:
        #         content = csv.DictReader(file)
        #         for target in content:
        #             account_id = target.get('AccountId', None)

        #             if account_id is None:
        #                 self.logging.error('AccountId not found')
        #                 sys.exit(1)
        target_item = self.get_target_item(self.account_id, self.region, "Account")
        items_list.append(target_item)

        # if self.org_file is not None and os.path.isfile(self.org_file):
        #     with open(self.org_file, mode='r') as file:
        #         content = csv.DictReader(file)
        #         for target in content:
        #             org_unit = target.get('OrgUnit', None)

        #             if org_unit is None:
        #                 self.logging.error('OrgUnit not found')
        #                 sys.exit(1)

        #             target_item = self.get_target_item(org_unit, target.get('Region'), 'Organizational Unit')

        #             items_list.append(target_item)

        if len(items_list) == 0:
            self.logging.error("Accounts not found")
            sys.exit(1)

        return items_list

    @staticmethod
    def get_target_item(account: str, region: str, account_type: str) -> dict:
        return {
            "Account": account,
            "Region": region,
            "AccountType": account_type,
            "ExecutionRoleName": DEFAULT_TARGET_SSM_EXECUTION_ROLE,
        }


if __name__ == "__main__":
    dynamodb_ops = DynamoDbOps()
    dynamodb_ops.insert_items()
