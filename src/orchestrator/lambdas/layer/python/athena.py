import os
import time
from datetime import date
from typing import Any, Optional

import boto3
from aws_lambda_powertools import Logger
from queries import METADATA_TABLE_NAME, AthenaQueries, get_table

# Environment Variables
ATHENA_DATABASE = os.getenv("ATHENA_DATABASE")
ATHENA_DATASOURCE = os.getenv("ATHENA_DATASOURCE")
ATHENA_QUERY_CACHING_MIN = int(os.getenv("ATHENA_QUERY_CACHING_MIN"))
S3_BUCKET = os.getenv("S3_BUCKET", None)

logger = Logger()
athena_client = boto3.client("athena")

# Constants
QUERY_RETRY_COUNT = (
    10  # The number of times to check the status of the Athena query execution.
)
CURRENT_DATE = date.today()


class ClusterPartition(object):

    def __init__(
        self, account_id: str, region: str, cluster_name: str, latest_data: str
    ):
        super().__init__()
        self.account_id = account_id
        self.region = region
        self.cluster_name = cluster_name
        self.latest_date = latest_data

    def __str__(self):
        return (
            f"AccountId: {self.account_id}; Region: {self.region}; ClusterName: {self.cluster_name}; "
            f"ReportDate{self.latest_date}"
        )

    def __hash__(self):
        return hash((self.account_id, self.region, self.cluster_name, self.latest_date))

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        return (
            self.account_id == other.account_id
            and self.region == other.region
            and self.cluster_name == other.cluster_name
            and self.latest_date == other.latest_date
        )


class AthenaTemplate:

    def __init__(self, database: str, query_cache: bool):
        self.database: str = database
        self.enable_query_cache: bool = query_cache

    def athena_query_execution(self, query: str) -> str:
        """
        Execute the Athena query and return the execution id.
        Also, wait for the Athena query to finish the execution

        Returns:
            str: Query Execution ID
        """

        # Execution
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={
                "Database": self.database,
                "Catalog": ATHENA_DATASOURCE,
            },
            ResultConfiguration={
                "OutputLocation": f"s3://{S3_BUCKET}/athena/queries/{CURRENT_DATE}"
            },
            ResultReuseConfiguration={
                "ResultReuseByAgeConfiguration": {
                    "Enabled": self.enable_query_cache,
                    "MaxAgeInMinutes": ATHENA_QUERY_CACHING_MIN,
                }
            },
        )

        query_execution_id = response["QueryExecutionId"]
        logger.info(f"Athena query execution id: {query_execution_id}")

        try:
            for i in range(1, 1 + QUERY_RETRY_COUNT):
                # get query execution
                query_status = athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                query_execution_status = query_status["QueryExecution"]["Status"][
                    "State"
                ]
                if query_execution_status == "SUCCEEDED":
                    logger.info(f"Record found for {query_execution_id}")
                    return query_execution_id

                if query_execution_status == "FAILED":
                    reason = query_status["QueryExecution"]["Status"][
                        "StateChangeReason"
                    ]
                    logger.info(
                        f"Execution failed for {query_execution_id} with error: {reason}"
                    )
                    logger.debug(query_status)
                    raise Exception(f"Query execution {query_execution_id}: {reason}")
                else:
                    time.sleep(i)

            athena_client.stop_query_execution(QueryExecutionId=query_execution_id)
            raise Exception(f"TIME OVER while executing query {query_execution_id}")
        except Exception as e:
            raise e

    def get_query_results(self, query: str) -> Any:
        """
        Get the query results.

        Returns:
            Any: Query results from table
        """

        logger.info(f"Executing query")
        logger.debug(f"Query: {query}")
        try:
            query_execution_id = self.athena_query_execution(query)
        except Exception as e:
            raise e

        try:
            logger.info("Fetching query results")
            athena_response = athena_client.get_query_results(
                QueryExecutionId=query_execution_id
            )
            logger.debug(f'Athena Rows: {athena_response["ResultSet"]["Rows"]}')

            return athena_response["ResultSet"]["Rows"]
        except Exception as e:
            logger.error(
                f"Exception while fetching query results for {query_execution_id}: {e}"
            )
            raise e


class ClusterRepository:

    def __init__(
        self,
        account_id: str,
        region: str,
        cluster_name: str,
        information: str,
        report_date: Optional[str],
        query_cache: bool,
        relative_date: bool,
    ):

        self.database: str = ATHENA_DATABASE
        self.account_id: str = account_id
        self.region: str = region
        self.cluster_name: str = cluster_name
        self.information: str = information
        self.query_cache: bool = query_cache

        self.athena_template: AthenaTemplate = AthenaTemplate(
            self.database, self.query_cache
        )

        self.latest_date = self.get_report_date(
            report_date=report_date,
            relative_date=relative_date,
            information=information,
        )

        logger.info(f"Fetching data for date: {self.latest_date}")

        self.athena_queries: AthenaQueries = AthenaQueries(
            database=self.database,
            account_id=account_id,
            region=region,
            cluster_name=cluster_name,
            information=information,
            latest_date=self.latest_date,
        )

    def extract_partition_data(self, row_data) -> (dict, ClusterPartition):
        logger.debug(f"Extracting partition data from {row_data}")
        account_id: str = row_data[0]["VarCharValue"]
        region: str = row_data[1]["VarCharValue"]
        cluster_name = row_data[2]["VarCharValue"]

        partition_data_dict: dict = dict(
            AccountId=account_id,
            Region=region,
            ClusterName=cluster_name,
            ReportDate=self.latest_date,
        )

        partition_object: ClusterPartition = ClusterPartition(
            account_id=account_id,
            region=region,
            cluster_name=cluster_name,
            latest_data=self.latest_date,
        )

        return partition_data_dict, partition_object

    def extract_cluster_data(self, row_data) -> dict:
        logger.debug(f"Extracting cluster data from {row_data}")

        partition_data, partition_object = self.extract_partition_data(row_data)

        return partition_data

    @staticmethod
    def get_existing_record(
        cluster_list: [], partition_object: ClusterPartition
    ) -> Optional[dict]:

        def condition(element: dict) -> bool:
            return (
                element["AccountId"] == partition_object.account_id
                and element["Region"] == partition_object.region
                and element["ClusterName"] == partition_object.cluster_name
                and element["ReportDate"] == partition_object.latest_date
            )

        filtered_data = filter(condition, cluster_list)

        data = list(filtered_data)
        if len(data) > 1:
            raise Exception("Duplicate records found in the cluster list")

        if len(data) == 0:
            return None

        return data[0]

    def get_report_date(
        self, report_date: Optional[str], relative_date: bool, information: str
    ) -> str:

        if report_date is not None:
            return report_date

        table_name: str = METADATA_TABLE_NAME

        if relative_date:
            table_name = get_table(information)

        logger.info(
            f"Fetching the latest date for which data is present from {table_name} table"
        )
        query: str = f"""
            SELECT MAX(date) FROM {table_name}
        """
        data = self.athena_template.get_query_results(query)
        return data[1]["Data"][0]["VarCharValue"]

    def get_clusters(self) -> []:
        logger.info(
            f"Fetching data for account: {self.account_id}; "
            f"region: {self.region}; cluster: {self.cluster_name}; date: {self.latest_date}; "
            f"information: {self.information}"
        )

        key, table_name, query, multi_row, extract_data = (
            self.athena_queries.get_athena_query()
        )
        logger.info(f"Key - {key}; table_name - {table_name}")

        cluster_rows = self.athena_template.get_query_results(query)
        logger.info(f"Found {len(cluster_rows[1:])} rows")

        cluster_list = list()
        partition_set = set()

        # Ignore the first row since it will be column names
        for row in cluster_rows[1:]:
            row_data = row["Data"]

            cluster_details, partition_object = self.extract_partition_data(row_data)
            cluster_details["EKSVersion"] = row_data[3]["VarCharValue"]
            cluster_details["Metadata"] = self.athena_queries.extract_metadata_data(
                row_data
            )

            if partition_object in partition_set:
                existing_record = self.get_existing_record(
                    cluster_list=cluster_list, partition_object=partition_object
                )

                if existing_record is None:
                    raise Exception(
                        f"Internal server error. Record is present in set but not in list"
                    )

                logger.debug(f"Existing records: {existing_record}")

                cluster_list.remove(existing_record)

                details: Optional[dict] = existing_record.get("Details", None)

                if details is not None:
                    information_details: Optional = details.get(key, None)
                    if information_details is not None:
                        details_list = list()

                        if isinstance(information_details, dict):
                            details_list.append(information_details)
                        elif isinstance(information_details, list):
                            details_list.extend(information_details)

                        details_list.append(extract_data(row_data))
                        existing_record["Details"][key] = details_list
                        cluster_list.append(existing_record)

            else:
                partition_set.add(partition_object)

                cluster_details["Details"] = {}
                if table_name != METADATA_TABLE_NAME:

                    if multi_row:
                        cluster_details["Details"][key] = [extract_data(row_data)]
                    else:
                        cluster_details["Details"][key] = extract_data(row_data)

                cluster_list.append(cluster_details)

        return cluster_list
