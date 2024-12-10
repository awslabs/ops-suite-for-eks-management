import argparse
import csv
import json
import logging
import os
import sys

import boto3

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("-p", "--profile", help="aws profile name")
arg_parser.add_argument("-r", "--region", help="aws region")
arg_parser.add_argument("-b", "--bucket", help="bucket name")
arg_parser.add_argument("-a", "--accounts", help="Tenant Account id")
arg_parser.add_argument("-o", "--orgs", help="Organisation account id")


class BucketPolicy:
    region: str = None
    aws_profile: str = None
    s3_bucket: str = None
    org_id: str = None
    account_id: str = None

    def __init__(self):
        self.logging = logging.getLogger("BucketPolicy")
        self.logging.setLevel(logging.INFO)
        self.logging.addHandler(logging.StreamHandler(sys.stdout))

        self.parse_arguments()

        if self.aws_profile is None:
            self.aws_profile = "default"

        self.logging.info(f"Using {self.aws_profile} aws profile")

        if self.account_id is None and self.org_id is None:
            self.logging.error("No target account id or organisation id passed.")
            sys.exit(1)

        session = boto3.Session(profile_name=self.aws_profile, region_name=self.region)
        self.s3_client = session.client("s3")

    def update_bucket_policy(self):
        policy = self.get_bucket_policy()
        self.s3_client.put_bucket_policy(
            Bucket=self.s3_bucket, Policy=json.dumps(policy)
        )
        self.logging.info(f"Added bucket policy for {self.s3_bucket}")

    def get_bucket_policy(self) -> dict:
        statement = list()
        if self.account_id is not None:
            statement.extend(self.individual_account_policy())

        # if self.org_id is not None:
        #     statement.extend(self.org_units_policy())

        if len(statement) == 0:
            print("Invalid parameters provided")
            sys.exit(1)

        policy = {"Version": "2012-10-17", "Statement": statement}

        return policy

    def parse_arguments(self):
        arguments = arg_parser.parse_args()
        self.aws_profile = arguments.profile
        self.region = arguments.region
        self.s3_bucket = arguments.bucket
        self.account_id = arguments.accounts
        self.org_id = arguments.orgs

    def get_account_principals(self) -> list:
        aws_principals = set()
        account_id_temp = self.account_id
        if account_id_temp is not None:
            aws_principals.add(f"arn:aws:iam::{account_id_temp}:root")
        else:
            self.logging.error("AccountId not present")
            sys.exit(1)

        return list(aws_principals)

    # def get_org_units(self) -> list:
    #     accounts = set()
    #     org_unit = self.org_id
    #     if org_unit is not None:
    #                 accounts.add(org_unit)
    #     else:
    #                 self.logging.error('OrgUnit not present')
    #                 sys.exit(1)

    #     return list(accounts)

    def individual_account_policy(self) -> list:
        # Create a bucket policy
        return [
            {
                "Sid": "CrossAccountObjectAccess",
                "Effect": "Allow",
                "Principal": {"AWS": self.get_account_principals()},
                "Action": ["s3:GetObject", "s3:PutObject", "s3:PutObjectAcl"],
                "Resource": f"arn:aws:s3:::{self.s3_bucket}/*",
            },
            {
                "Sid": "CrossAccountBucketAccess",
                "Effect": "Allow",
                "Principal": {"AWS": self.get_account_principals()},
                "Action": "s3:ListBucket",
                "Resource": f"arn:aws:s3:::{self.s3_bucket}",
            },
        ]

    def org_units_policy(self) -> list:
        # Create a bucket policy
        return [
            {
                "Sid": "CrossAccountObjectAccess",
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject", "s3:PutObject", "s3:PutObjectAcl"],
                "Resource": f"arn:aws:s3:::{self.s3_bucket}/*",
            },
            {
                "Sid": "CrossAccountBucketAccess",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:ListBucket",
                "Resource": f"arn:aws:s3:::{self.s3_bucket}",
            },
        ]


if __name__ == "__main__":
    bucket_policy = BucketPolicy()
    bucket_policy.update_bucket_policy()
