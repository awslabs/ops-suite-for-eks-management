import csv
import json
import sys
from typing import AnyStr

from flatten_json import flatten
from prettytable import PrettyTable

from .inputcluster import InputCluster

# Constants
"""
Path of the region file
"""
REGION_FILE: str = "config/region.txt"

"""
Path of the cluster file
"""
CLUSTERS_FILE: str = "config/clusters.json"


class Progress:
    """
    Model class used to track the count of components updated in the EKS Cluster
    """

    _total: int = 0
    _updated: int = 0
    _failed: int = 0
    _no_action: int = 0
    _not_active: int = 0
    _not_requested: int = 0
    _not_supported: int = 0

    @property
    def total(self) -> int:
        return self._total

    def total_increment(self):
        self._total += 1

    @property
    def updated(self) -> int:
        return self._updated

    def updated_increment(self, count: int = 1):
        self._updated += count

    @property
    def failed(self) -> int:
        return self._failed

    def failed_increment(self, count: int = 1):
        self._failed += count

    @property
    def no_action(self) -> int:
        return self._no_action

    def no_action_increment(self, count: int = 1):
        self._no_action += count

    @property
    def not_active(self) -> int:
        return self._not_active

    def not_active_increment(self, count: int = 1):
        self._not_active += count

    @property
    def not_requested(self) -> int:
        return self._not_requested

    def not_requested_increment(self, count: int = 1):
        self._not_requested += count

    @property
    def not_supported(self) -> int:
        return self._not_supported

    def not_supported_increment(self, count: int = 1):
        self._not_supported += count


class FileUtility:
    """
    Utility related to file operations.
    """

    @staticmethod
    def read_file(file: str) -> AnyStr:
        """
        Read file content and return the same.

        Args:
            file: Complete file path to read content from.

        Returns:
            AnyStr: File contents
        """

        with open(file) as f:
            return f.read()

    @staticmethod
    def write_file(file: str, content: AnyStr) -> None:
        """
        Write the given content to the file.

        Args:
            file: Complete file path to write content.
            content: Data to write to a file

        Returns:
            None
        """

        with open(file, "w") as f:
            f.write(content)

    @staticmethod
    def read_json_file(file: str) -> dict:
        """
        Read file content and convert it into a dict for easier use.

        Args:
            file: Complete file path to read content from.

        Returns:
            dict: File content as a dict
        """

        return json.loads(FileUtility.read_file(file))

    @staticmethod
    def write_json(file: str, content: dict) -> None:
        """
        Write the given content to the file as a json.

        Args:
            file: Complete file path to write content.
            content: Data to write to a file

        Returns:
            None
        """

        FileUtility.write_file(file, json.dumps(content))

    @staticmethod
    def write_yaml(file: str, yaml_content) -> None:
        """

        Args:
            file: Complete file path to write content.
            yaml_content: YAML content to write to file.

        Returns:
            None
        """

        FileUtility.write_file(file, yaml_content)

    @staticmethod
    def write_flatten_json(file: str, content: dict) -> None:
        """

        Args:
            file: Complete file path to write content.
            content:  Flattened json content to write to file.

        Returns:
            None
        """

        flatten_content = flatten(content, "_")
        FileUtility.write_json(file, flatten_content)

    @staticmethod
    def write_csv(file: str, content: [dict]) -> None:
        """
        Write the CSV content to a CSV file.

        Args:
            file: Complete file path to write content.
            content: CSV content to write to file.

        Returns:
            None
        """

        if content is None:
            return

        data_file = open(file, "w", newline="")
        csv_writer = csv.writer(data_file)

        count = 0
        for data in content:
            if count == 0:
                header = list(data)
                header.insert(0, "Id")
                csv_writer.writerow(header)
            count += 1
            row = list(data.values())
            row.insert(0, count)
            csv_writer.writerow(row)

        data_file.close()

    @staticmethod
    def write_csv_headers(file: str, headers: [], dummy_row: []) -> None:
        """
         Write empty CSV content to a CSV file.

        Args:
            file: Complete file path to write content.
            headers: CSV Headers
            dummy_row: Row to write to the file.

        Returns:
            None
        """

        data_file = open(file, "w", newline="")
        csv_writer = csv.writer(data_file)
        csv_writer.writerow(headers)
        csv_writer.writerow(dummy_row)

        data_file.close()

    @staticmethod
    def to_dict(table: PrettyTable) -> dict:
        """
        Convert PrettyTable object to a dict

        Args:
            table: Pretty table

        Returns:
            dict: table to dict
        """

        json_str = table.get_json_string()
        table_dict = json.loads(json_str)
        table_dict.pop(0)
        return table_dict


class ClusterUtility:
    """
    Utility related to cluster operations.
    """

    @staticmethod
    def from_strings(clusters: [str]) -> [InputCluster]:
        """
        Convert a list of cluster strings to a list of InputCluster objects.

        Args:
            clusters: List of clusters

        Returns:
            []: List of InputCluster objects.
        """

        formatted_clusters: [InputCluster] = []
        for cluster in clusters:
            input_cluster = InputCluster(input_cluster=dict(ClusterName=cluster))
            formatted_clusters.append(input_cluster)

        return formatted_clusters

    @staticmethod
    def from_dicts(clusters: [dict]) -> [InputCluster]:
        """
        Convert a list of input cluster passed from SSM Automation to a list of InputCluster objects.

        Args:
            clusters: List of input clusters

        Returns:
            []: List of InputCluster objects.
        """

        list_clusters: [InputCluster] = []

        for cluster_dict in clusters:
            obj: InputCluster = InputCluster(input_cluster=cluster_dict)
            list_clusters.append(obj)

        return list_clusters

    @staticmethod
    def filter_clusters(
        valid_account_clusters: [str],
        input_clusters: [dict],
        account_id: str,
        region: str,
    ) -> []:
        """
        Filter input clusters by account and region and clusters present in config/clusters.json file

        Args:
            valid_account_clusters: List of clusters fetched from config/clusters.json file
            input_clusters: List of input clusters passed from SSM Automation
            account_id: AWS Account ID
            region: AWS Region

        Returns:
            []: List of input clusters
        """

        return [
            i
            for i in input_clusters
            if i.get("ClusterName") in valid_account_clusters
            and account_id == i.get("AccountId", None)
            and region == i.get("Region", None)
        ]

    @staticmethod
    def get_relevant_clusters(
        filter_input_clusters: bool,
        valid_account_clusters: [str],
        input_clusters: [dict],
        account_id: str,
        region: str,
    ) -> [InputCluster]:
        """

        Args:
            filter_input_clusters: Weather the clusters need to be filtered.
            valid_account_clusters: List of clusters fetched from config/clusters.json file
            input_clusters: List of input clusters passed from SSM Automation
            account_id: AWS Account ID
            region: AWS Region

        Returns:
            []: List of InputCluster cluster objects
        """

        if filter_input_clusters:
            filtered_clusters = ClusterUtility.filter_clusters(
                valid_account_clusters=valid_account_clusters,
                input_clusters=input_clusters,
                account_id=account_id,
                region=region,
            )
            return ClusterUtility.from_dicts(filtered_clusters)
        else:
            return ClusterUtility.from_strings(valid_account_clusters)


class ExecutionUtility:
    """
    Utility related to SSM Automation execution operations.
    """

    @staticmethod
    def stop() -> None:
        """
        Exit from the SSM Automation execution.

        Returns:
            None
        """

        sys.exit(1)
