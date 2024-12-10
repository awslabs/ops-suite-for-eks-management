from ..lib.basestep import BaseStep
from ..lib.ekshelper import EKSHelper
from ..lib.inputcluster import InputCluster
from ..lib.wfutils import ExecutionUtility, FileUtility
from .constants import DEPRECATED_APIS_STEP, LOG_FOLDER, S3_FOLDER_NAME


def write_empty_file(report_file: str):
    headers = [
        "Id",
        "Name",
        "ApiVersion",
        "RuleSet",
        "ReplaceWith",
        "SinceVersion",
        "StopVersion",
        "RequestsInLast30Days",
        "Message",
        "Data",
    ]
    dummy_row = [
        1,
        None,
        None,
        None,
        None,
        None,
        None,
        0,
        "No deprecated API found",
        "N/A",
    ]
    FileUtility.write_csv_headers(report_file, headers, dummy_row)


def get_deprecated_api_content(
    insight_details: dict,
    deprecated: dict,
    insight_name: str,
    message: str,
    data: str = "A",
) -> dict:
    usage = deprecated.get("usage")
    replace_with = deprecated.get("replacedWith")
    since_version = deprecated.get("startServingReplacementVersion")
    stop_version = deprecated.get("stopServingVersion")
    client_stats = deprecated.get("clientStats", [])

    requests_in_last_30_days = 0
    if len(client_stats) > 0:
        for client_stat in client_stats:
            requests_in_last_30_days += int(
                client_stat.get("numberOfRequestsLast30Days")
            )

    name_arr = usage.split("/")
    name = name_arr[len(name_arr) - 1]

    api_version = f"{name_arr[2]}/{name_arr[3]}"

    insights_status_details = insight_details.get("insightStatus", {})
    insights_status = insights_status_details.get("status", None)

    return dict(
        Name=name,
        ApiVersion=api_version,
        RuleSet=insight_name,
        ReplaceWith=replace_with,
        SinceVersion=f"{since_version}",
        StopVersion=f"{stop_version}",
        RequestsInLast30Days=requests_in_last_30_days,
        InsightStatus=insights_status,
        Message=message,
        Data=data,
    )


class DeprecatedAPIsStep(BaseStep):
    eks_helper: EKSHelper = None

    def __init__(self):
        super().__init__(
            step_name=DEPRECATED_APIS_STEP,
            s3_folder=S3_FOLDER_NAME,
            log_prefix=LOG_FOLDER,
        )
        self.eks_helper = EKSHelper(region=self.region, calling_module=self._step_name)

    def run(self, input_cluster: InputCluster = None):
        cluster = input_cluster.cluster
        csv_report = self.csv_report_file(
            cluster=cluster, report_name=DEPRECATED_APIS_STEP
        )
        try:
            insights = self.eks_helper.list_insights(
                cluster_name=cluster, kubernetes_version=self.eks_version
            )

            if len(insights) == 0:
                self.logger.info("No Insights related to update readiness")
                write_empty_file(csv_report)
            else:
                report = []
                for insight in insights:
                    insight_id = insight.get("id")
                    insight_name = insight.get("name")

                    insight_details = self.eks_helper.describe_insight(
                        cluster_name=cluster, insight_id=insight_id
                    )

                    upgrade_specific_summary = insight_details.get(
                        "categorySpecificSummary"
                    )
                    deprecation_details = upgrade_specific_summary.get(
                        "deprecationDetails", []
                    )
                    recommendation = insight_details.get("recommendation")

                    if len(deprecation_details) > 0:
                        for deprecated in deprecation_details:
                            report.append(
                                get_deprecated_api_content(
                                    insight_details,
                                    deprecated,
                                    insight_name,
                                    recommendation,
                                )
                            )

                if len(report) == 0:
                    write_empty_file(csv_report)
                else:
                    FileUtility.write_csv(csv_report, report)

        except Exception as e:
            self.logger.error(
                f"Error while checking deprecated APIs for {cluster}: {e}"
            )
            ExecutionUtility.stop()


if __name__ == "__main__":
    deprecated_apis_step = DeprecatedAPIsStep()
    deprecated_apis_step.start(
        name=DEPRECATED_APIS_STEP,
        report_name=DEPRECATED_APIS_STEP,
        for_each_cluster=True,
        filter_input_clusters=True,
        input_clusters_required=False,
        check_cluster_status=False,
    )
