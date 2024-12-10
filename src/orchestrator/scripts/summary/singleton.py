from kubernetes import client
from prettytable import PrettyTable

from ..lib.basestep import BaseStep
from ..lib.inputcluster import InputCluster
from ..lib.wfutils import ExecutionUtility, FileUtility
from .constants import (
    DAEMONSET_NAME,
    IGNORE_LIVENESS_READINESS_DEPLOYMENTS,
    LOG_FOLDER,
    NEED_DAEMONSET_NODE,
    NEED_LIVENESS_AND_READINESS_PROBE,
    NEED_NODE_AFFINITIES,
    RESTRICTED_NAMESPACES,
    S3_FOLDER_NAME,
    SINGLETON_STEP,
)


class SingletonStep(BaseStep):
    _step_name = "singleton"

    def __init__(self):
        super().__init__(
            step_name=SINGLETON_STEP, s3_folder=S3_FOLDER_NAME, log_prefix=LOG_FOLDER
        )

    def run(self, input_cluster: InputCluster = None):
        cluster = input_cluster.cluster

        csv_report = self.csv_report_file(cluster=cluster, report_name=SINGLETON_STEP)

        table = PrettyTable()
        table.field_names = ["Resource", "Namespace", "Name", "Data"]

        try:
            core_api: client.CoreV1Api = self.kube_core_api_client(cluster)
            apps_api: client.AppsV1Api = self.kube_apps_api_client(cluster)

            namespaces = core_api.list_namespace()

            self.logger.info(f"Fetching singleton deployments for {cluster}")
            singleton_deployments = self.get_singleton_deployments(namespaces, apps_api)
            if len(singleton_deployments) != 0:
                table.add_rows(singleton_deployments)

            self.logger.info(f"Fetching singleton statefulsets for {cluster}")
            singleton_statefulsets = self.get_singleton_statefulsets(
                namespaces, apps_api
            )
            if len(singleton_statefulsets) != 0:
                table.add_rows(singleton_statefulsets)

            self.logger.info(f"Fetching single node deployments for {cluster}")
            single_node_deployments = self.get_single_node_deployments(
                namespaces, apps_api, core_api
            )
            if len(single_node_deployments) != 0:
                table.add_rows(single_node_deployments)

            if NEED_LIVENESS_AND_READINESS_PROBE:
                self.logger.info(
                    f"Fetching deployments without liveness and readiness probes for {cluster}"
                )
                liveness_readiness_deployments = (
                    self.get_liveness_readiness_deployments(namespaces, apps_api)
                )
                if len(liveness_readiness_deployments) != 0:
                    table.add_rows(liveness_readiness_deployments)

            if NEED_NODE_AFFINITIES:
                self.logger.info(
                    f"Fetching deployments with and without node affinities for {cluster}"
                )
                node_affinity_deployments = self.get_node_affinity_deployments(
                    namespaces, apps_api
                )
                if len(node_affinity_deployments) != 0:
                    table.add_rows(node_affinity_deployments)

            if NEED_DAEMONSET_NODE:
                self.logger.info(f"Fetching nodes with daemonsets for {cluster}")
                daemonset_nodes = self.get_daemonset_nodes(core_api)
                if len(daemonset_nodes) != 0:
                    table.add_rows(daemonset_nodes)

            table_content = FileUtility.to_dict(table)

            if table_content is not None and len(table_content) != 0:
                FileUtility.write_csv(csv_report, table_content)
            else:
                headers = ["Id", "Resource", "Namespace", "Name", "Data"]
                dummy_row = [1, None, None, None, "N/A"]
                FileUtility.write_csv_headers(csv_report, headers, dummy_row)

        except Exception as e:
            self.logger.error(
                f"Error while fetching singleton resources for {cluster}: {e}"
            )
            ExecutionUtility.stop()

    def get_singleton_deployments(
        self, namespaces: any, apps_api: client.AppsV1Api
    ) -> []:
        tables_rows = []
        apps_with_single_rs = []
        deployments_with_single_replica = {}

        for namespace in namespaces.items:
            get_name_space = namespace.metadata.name

            deployments = apps_api.list_namespaced_deployment(namespace=get_name_space)

            if namespace.metadata.name not in RESTRICTED_NAMESPACES:
                for deployment in deployments.items:
                    deployment = apps_api.read_namespaced_deployment(
                        deployment.metadata.name, get_name_space
                    )
                    replicas = deployment.spec.replicas
                    if replicas == 1:
                        apps_with_single_rs.append(deployment.metadata.name)
                        if get_name_space in deployments_with_single_replica:
                            deployments_with_single_replica[get_name_space].append(
                                deployment.metadata.name
                            )
                        else:
                            deployments_with_single_replica[get_name_space] = [
                                deployment.metadata.name
                            ]

        self.logger.info(
            f"Total Number of Applications (Deployments) running with Single Replicas : {len(apps_with_single_rs)}\n"
        )

        if len(deployments_with_single_replica.items()) != 0:
            for namespace, deployments in deployments_with_single_replica.items():
                tables_rows.append(
                    [
                        "DeploymentsWithSingleReplica",
                        namespace,
                        "\n".join(deployments),
                        "A",
                    ]
                )

        return tables_rows

    def get_singleton_statefulsets(
        self, namespaces: any, apps_api: client.AppsV1Api
    ) -> []:
        tables_rows = []
        st_apps_with_single_rs = []
        statefulset_with_single_replica = {}

        for namespace in namespaces.items:
            get_name_space = namespace.metadata.name

            stateful_set = apps_api.list_namespaced_stateful_set(
                namespace=get_name_space
            )

            if namespace.metadata.name not in RESTRICTED_NAMESPACES:
                for st in stateful_set.items:
                    replicas = st.spec.replicas
                    if replicas == 1:
                        st_apps_with_single_rs.append(st.metadata.name)
                        if get_name_space in statefulset_with_single_replica:
                            statefulset_with_single_replica[get_name_space].append(
                                st.metadata.name
                            )
                        else:
                            statefulset_with_single_replica[get_name_space] = [
                                st.metadata.name
                            ]

        self.logger.info(
            f"Total Number of Applications (Statefulsets) running with Single Replicas : "
            f"{len(st_apps_with_single_rs)}\n"
        )

        if len(statefulset_with_single_replica.items()) != 0:
            for namespace, deployments in statefulset_with_single_replica.items():
                tables_rows.append(
                    [
                        "StatefulSetsWithSingleReplica",
                        namespace,
                        "\n".join(deployments),
                        "A",
                    ]
                )

        return tables_rows

    def get_single_node_deployments(
        self, namespaces: any, apps_api: client.AppsV1Api, core_api: client.CoreV1Api
    ) -> []:
        tables_rows = []
        deployment_single_node = {}

        for namespace in namespaces.items:
            namespace_name = namespace.metadata.name
            deployments = apps_api.list_namespaced_deployment(namespace_name).items

            for deployment in deployments:
                deployment_name = deployment.metadata.name
                pods = core_api.list_namespaced_pod(
                    namespace_name, label_selector=f"app={deployment_name}"
                ).items
                replicas = deployment.spec.replicas
                if replicas > 1:
                    if not pods:
                        continue
                    node_name = pods[0].spec.node_name
                    for pod in pods:
                        if pod.spec.node_name != node_name:
                            break
                    else:
                        if namespace_name in deployment_single_node:
                            deployment_single_node[namespace_name].append(
                                deployment_name
                            )
                        else:
                            deployment_single_node[namespace_name] = [deployment_name]

        no_single_nodes = len(deployment_single_node.items())
        self.logger.info(
            f"Number of Applications (Deployments) running with Single nodes : {no_single_nodes}\n"
        )

        if no_single_nodes != 0:
            for namespace, deployments in deployment_single_node.items():
                tables_rows.append(
                    [
                        "DeploymentsWithSingleNode",
                        namespace,
                        "\n".join(deployments),
                        "A",
                    ]
                )

        return tables_rows

    def get_liveness_readiness_deployments(
        self, namespaces: any, apps_api: client.AppsV1Api
    ) -> []:
        table_rows = []
        deployment_liveness_probe = {}
        deployment_readiness_probe = {}

        for namespace in namespaces.items:
            namespace_name = namespace.metadata.name

            deployments = apps_api.list_namespaced_deployment(namespace_name).items

            for deployment in deployments:
                if (
                    namespace_name not in RESTRICTED_NAMESPACES
                    and deployment.metadata.name
                    not in IGNORE_LIVENESS_READINESS_DEPLOYMENTS
                ):
                    deployment_name = deployment.metadata.name
                    containers = deployment.spec.template.spec.containers
                    for container in containers:
                        if not container.readiness_probe:
                            print(
                                f"Deployment {deployment_name} in namespace {namespace_name} doesnt not have readiness "
                                f"probe"
                            )
                            if namespace_name in deployment_readiness_probe:
                                deployment_readiness_probe[namespace_name].append(
                                    deployment_name
                                )
                            else:
                                deployment_readiness_probe[namespace_name] = [
                                    deployment_name
                                ]
                        if not container.liveness_probe:
                            print(
                                f"Deployment {deployment_name} in namespace {namespace_name} doesnt not have liveness "
                                f"probe"
                            )
                            if namespace_name in deployment_liveness_probe:
                                deployment_liveness_probe[namespace_name].append(
                                    deployment_name
                                )
                            else:
                                deployment_liveness_probe[namespace_name] = [
                                    deployment_name
                                ]

        no_deployments_without_readiness = len(deployment_readiness_probe.items())
        self.logger.info(
            f"Number of Applications (Deployments) not running with readiness probe : "
            f"{no_deployments_without_readiness}\n"
        )
        if no_deployments_without_readiness != 0:
            for namespace, deployments in deployment_readiness_probe.items():
                table_rows.append(
                    [
                        "DeploymentsWithoutReadinessProbe",
                        namespace,
                        "\n".join(deployments),
                        "A",
                    ]
                )

        no_deployments_without_liveness = len(deployment_liveness_probe.items())
        self.logger.info(
            f"Number of Applications (Deployments) not running with readiness probe : "
            f"{no_deployments_without_liveness}\n"
        )
        if no_deployments_without_liveness != 0:
            for namespace, deployments in deployment_liveness_probe.items():
                table_rows.append(
                    [
                        "DeploymentsWithoutLivenessProbe",
                        namespace,
                        "\n".join(deployments),
                        "A",
                    ]
                )

        return table_rows

    def get_node_affinity_deployments(
        self, namespaces: any, apps_api: client.AppsV1Api
    ) -> []:
        table_rows = []
        deployments_with_node_affinity = {}
        deployments_without_node_affinity = {}

        for name_space in namespaces.items:
            namespace = name_space.metadata.name
            if namespace not in RESTRICTED_NAMESPACES:
                deploy_list = apps_api.list_namespaced_deployment(namespace)

                for deploy in deploy_list.items:
                    deployment = deploy.metadata.name
                    deploy_affinity = deploy.spec.template.spec.affinity
                    if deploy_affinity and deploy_affinity.node_affinity:
                        if name_space.metadata.name in deployments_with_node_affinity:
                            deployments_with_node_affinity[
                                name_space.metadata.name
                            ].append(deployment)
                        else:
                            deployments_with_node_affinity[name_space.metadata.name] = [
                                deployment
                            ]
                    if deploy_affinity is None:
                        if (
                            name_space.metadata.name
                            in deployments_without_node_affinity
                        ):
                            deployments_without_node_affinity[
                                name_space.metadata.name
                            ].append(deployment)

                        else:
                            deployments_without_node_affinity[
                                name_space.metadata.name
                            ] = [deployment]

        no_deployments_with_node_affinity = len(deployments_with_node_affinity.items())
        self.logger.info(
            f"Number of Applications (Deployments) running with node affinity : {no_deployments_with_node_affinity}\n"
        )
        if no_deployments_with_node_affinity != 0:
            for namespace, deployments in deployments_with_node_affinity.items():
                table_rows.append(
                    [
                        "DeploymentsWithNodeAffinity",
                        namespace,
                        "\n".join(deployments),
                        "A",
                    ]
                )

        no_deployments_without_node_affinity = len(
            deployments_without_node_affinity.items()
        )
        self.logger.info(
            f"Number of Applications (Deployments) running without node affinity : "
            f"{no_deployments_without_node_affinity}\n"
        )
        if no_deployments_without_node_affinity != 0:
            for namespace, deployments in deployments_without_node_affinity.items():
                table_rows.append(
                    [
                        "DeploymentsWithoutNodeAffinity",
                        namespace,
                        "\n".join(deployments),
                        "A",
                    ]
                )

        return table_rows

    def get_daemonset_nodes(self, core_api: client.CoreV1Api) -> []:
        table_rows = []
        eks_node_daemonset = {}

        nodes = core_api.list_node().items
        if nodes is None or len(nodes) == 0:
            self.logger.warning(f"No nodes present")
            return table_rows

        for node in nodes:
            node_name = node.metadata.name
            pods = core_api.list_pod_for_all_namespaces(
                field_selector=f"spec.nodeName={node_name}"
            ).items

            for pod in pods:
                if (
                    pod.metadata.owner_references
                    and pod.metadata.owner_references[0].kind == "DaemonSet"
                ):
                    node_daemon_set_name = pod.metadata.owner_references[0].name
                    if node_name not in eks_node_daemonset:
                        eks_node_daemonset[node_name] = []
                    eks_node_daemonset[node_name].append(node_daemon_set_name)

            no_daemonset_nodes = len(eks_node_daemonset.items())
            self.logger.info(f"Number of DaemonSet Pods : {no_daemonset_nodes}\n")

            if no_daemonset_nodes != 0:
                for key, values in eks_node_daemonset.items():
                    if DAEMONSET_NAME not in eks_node_daemonset[key]:
                        table_rows.append(
                            [
                                "NodesWithEBSDaemonset",
                                "\n".join("N/A"),
                                "\n".join(key),
                                "A",
                            ]
                        )

            return table_rows


if __name__ == "__main__":
    singleton_step = SingletonStep()
    singleton_step.start(
        name=SINGLETON_STEP,
        report_name=SINGLETON_STEP,
        for_each_cluster=True,
        filter_input_clusters=True,
        input_clusters_required=False,
        check_cluster_status=False,
    )
