from cluster import Cluster, logger
from dynamodb import DynamodbTargets
from event import (
    BackupEventSource,
    EventTargets,
    RestoreEventSource,
    SummaryEventSource,
    UpgradeEventSource,
)
from target import Target

# Constants
SUMMARY_KEY: str = "Summary"
BACKUP_KEY: str = "Backup"
RESTORE_KEY: str = "Restore"
UPGRADE_KEY: str = "Upgrade"


def get_target_locations(event: dict, eks_clusters: [Cluster]) -> [Target]:
    """
    Get target locations. If no targets are found in the lambda event, fetch the same from dynamodb and return

    Args:
        event: Lambda event
        eks_clusters: Array of input EKS clusters

    Returns:
        []: List of Targets
    """

    input_targets = event.get("Targets", [])

    if len(input_targets) == 0:
        return DynamodbTargets().get_locations_using_clusters(eks_clusters)
    else:
        return EventTargets(input_targets).get_locations()


def get_input_clusters(
    lambda_name: str, event: dict, default_options: dict
) -> [Cluster]:
    """
    Get the input clusters based on the source provided in the event.

    Args:
        lambda_name: Name of the lambda function
        event: Lambda event
        default_options: Default options for input clusters.

    Returns:
        []: List of Clusters
    """

    clusters: [Cluster] = []

    input_clusters = event.get("Clusters", {})
    summary_clusters = input_clusters.get(SUMMARY_KEY, [])
    upgrade_clusters = input_clusters.get(UPGRADE_KEY, [])
    backup_clusters = input_clusters.get(BACKUP_KEY, [])
    restore_clusters = input_clusters.get(RESTORE_KEY, [])

    logger.info(f"Input clusters - {input_clusters}")

    if BACKUP_KEY.upper() in lambda_name.upper():

        if len(backup_clusters) > 0:
            logger.info(f"Getting {len(backup_clusters)} backup clusters from event")
            event_source: BackupEventSource = BackupEventSource(
                backup_clusters, default_options
            )
            clusters.extend(event_source.get_clusters())

        if len(restore_clusters) > 0:
            logger.info(f"Getting {len(restore_clusters)} restore clusters from event")
            event_source: RestoreEventSource = RestoreEventSource(
                restore_clusters, default_options
            )
            clusters.extend(event_source.get_clusters())

    elif UPGRADE_KEY.upper() in lambda_name.upper():

        if len(upgrade_clusters) > 0:
            logger.info(f"Getting {len(restore_clusters)} restore clusters from event")
            event_source: UpgradeEventSource = UpgradeEventSource(
                upgrade_clusters, default_options
            )
            clusters = event_source.get_clusters()

    elif SUMMARY_KEY.upper() in lambda_name.upper():

        if len(summary_clusters) > 0:
            logger.info(f"Getting {len(summary_clusters)} summary clusters from event")
            event_source: SummaryEventSource = SummaryEventSource(summary_clusters, {})
            clusters = event_source.get_clusters()

    return clusters
