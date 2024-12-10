import { Fn, Stack, StackProps } from "aws-cdk-lib";
import { Quicksight } from "./config/OrchestratorConfig";
import { Construct } from "constructs";
import { CfnDataSet, CfnDataSource } from "aws-cdk-lib/aws-quicksight";
import {
  Effect,
  IRole,
  Policy,
  PolicyStatement,
  Role,
} from "aws-cdk-lib/aws-iam";
import {
  getAthenaWorkGroupName,
  getGlueDatabaseName,
} from "./orchestrator/iac/Utils";

export interface QuicksightStackProps extends StackProps {
  readonly config: Quicksight;
  readonly s3BucketName: string;
  readonly summaryEnabled: boolean;
  readonly backupEnabled: boolean;
  readonly upgradeEnabled: boolean;
}

export class QuicksightStack extends Stack {
  constructor(
    scope: Construct,
    id: string,
    resourcePrefix: string,
    props: QuicksightStackProps,
  ) {
    super(scope, id, props);

    const accountId: string = Fn.sub("${AWS::AccountId}");

    const defaultIamRole: string = "aws-quicksight-service-role-v0";
    const defaultIamRoleArn = `arn:aws:iam::${accountId}:role/service-role/${defaultIamRole}`;
    const roleArn = props.config.quickSightIAMRoleArn ?? defaultIamRoleArn;
    const quicksightRole: IRole = Role.fromRoleArn(
      this,
      "eks-quicksight-role",
      roleArn,
    );

    const bucketArn = `arn:aws:s3:::${props.s3BucketName}`;

    const policy: Policy = this.quicksightPolicy(bucketArn);
    quicksightRole.attachInlinePolicy(policy);

    let athenaDataSource: CfnDataSource = this.athenaDataSource(
      accountId,
      resourcePrefix,
      props.config,
    );

    const quicksightProps: Quicksight = {
      ...props.config,
      athenaWorkGroup:
        props.config.athenaWorkGroup ?? getAthenaWorkGroupName(resourcePrefix),
      databaseName:
        props.config.databaseName ?? getGlueDatabaseName(resourcePrefix),
    };

    if (props.summaryEnabled) {
      let addonDataset: CfnDataSet = this.addonDataset(
        accountId,
        resourcePrefix,
        athenaDataSource.attrArn,
        quicksightProps,
      );
      let csrDataset: CfnDataSet = this.csrDataSet(
        accountId,
        resourcePrefix,
        athenaDataSource.attrArn,
        quicksightProps,
      );
      let deprecatedApIsDataSet: CfnDataSet = this.deprecatedApIsDataSet(
        accountId,
        resourcePrefix,
        athenaDataSource.attrArn,
        quicksightProps,
      );
      let metadataDataSet: CfnDataSet = this.metadataDataSet(
        accountId,
        resourcePrefix,
        athenaDataSource.attrArn,
        quicksightProps,
      );
      let pspDataSet: CfnDataSet = this.pspDataSet(
        accountId,
        resourcePrefix,
        athenaDataSource.attrArn,
        quicksightProps,
      );
      let singletonResourcesDataSet: CfnDataSet =
        this.singletonResourcesDataSet(
          accountId,
          resourcePrefix,
          athenaDataSource.attrArn,
          quicksightProps,
        );
      let unhealthyPodsDataSet: CfnDataSet = this.unhealthyPodsDataSet(
        accountId,
        resourcePrefix,
        athenaDataSource.attrArn,
        quicksightProps,
      );
      let workerNodesDataSet: CfnDataSet = this.workerNodesDataSet(
        accountId,
        resourcePrefix,
        athenaDataSource.attrArn,
        quicksightProps,
      );

      addonDataset.addDependency(athenaDataSource);
      csrDataset.addDependency(athenaDataSource);
      deprecatedApIsDataSet.addDependency(athenaDataSource);
      metadataDataSet.addDependency(athenaDataSource);
      pspDataSet.addDependency(athenaDataSource);
      singletonResourcesDataSet.addDependency(athenaDataSource);
      unhealthyPodsDataSet.addDependency(athenaDataSource);
      workerNodesDataSet.addDependency(athenaDataSource);
    }

    if (props.backupEnabled) {
      let backupRestoreDataSet: CfnDataSet = this.backupRestoreDataSet(
        accountId,
        resourcePrefix,
        athenaDataSource.attrArn,
        quicksightProps,
      );
      backupRestoreDataSet.addDependency(athenaDataSource);
    }

    if (props.upgradeEnabled) {
      let addonUpgradeDataSet: CfnDataSet = this.addonUpgradeDataSet(
        accountId,
        resourcePrefix,
        athenaDataSource.attrArn,
        quicksightProps,
      );
      let clusterUpgradeDataSet: CfnDataSet = this.clusterUpgradeDataSet(
        accountId,
        resourcePrefix,
        athenaDataSource.attrArn,
        quicksightProps,
      );
      let nodegroupUpgradeDataSet: CfnDataSet = this.nodegroupUpgradeDataSet(
        accountId,
        resourcePrefix,
        athenaDataSource.attrArn,
        quicksightProps,
      );
      let postUpgradeDataSet: CfnDataSet = this.postUpgradeDataSet(
        accountId,
        resourcePrefix,
        athenaDataSource.attrArn,
        quicksightProps,
      );

      addonUpgradeDataSet.addDependency(athenaDataSource);
      clusterUpgradeDataSet.addDependency(athenaDataSource);
      nodegroupUpgradeDataSet.addDependency(athenaDataSource);
      postUpgradeDataSet.addDependency(athenaDataSource);
    }
  }

  athenaDataSource(
    accountId: string,
    resourcePrefix: string,
    props: Quicksight,
  ): CfnDataSource {
    return new CfnDataSource(this, "AthenaDataSource", {
      dataSourceId: `${resourcePrefix}-athena-ds`,
      name: "EKS Summary Athena DS",
      awsAccountId: `${accountId}`,
      type: "ATHENA",
      dataSourceParameters: {
        athenaParameters: {
          workGroup: props.athenaWorkGroup,
        },
      },
      sslProperties: {
        disableSsl: false,
      },
      permissions: [
        {
          principal: props.quickSightUserArn,
          actions: [
            "quicksight:UpdateDataSourcePermissions",
            "quicksight:DescribeDataSource",
            "quicksight:DescribeDataSourcePermissions",
            "quicksight:PassDataSource",
            "quicksight:UpdateDataSource",
            "quicksight:DeleteDataSource",
          ],
        },
      ],
    });
  }

  quicksightPolicy(bucketArn: string): Policy {
    return new Policy(this, "eks-quicksight-s3-permissions", {
      policyName: "eks-reports-s3-permissions",
      statements: [
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: ["s3:ListAllMyBuckets"],
          resources: ["arn:aws:s3:::*"],
        }),
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: [
            "s3:ListBucket",
            "s3:ListBucketMultipartUploads",
            "s3:GetBucketLocation",
          ],
          resources: [bucketArn],
        }),
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: [
            "s3:GetObject",
            "s3:GetObjectVersion",
            "s3:PutObject",
            "s3:AbortMultipartUpload",
            "s3:ListMultipartUploadParts",
          ],
          resources: [`${bucketArn}/*`],
        }),
      ],
    });
  }

  addonDataset(
    accountId: string,
    resourcePrefix: string,
    datasourceArn: string,
    props: Quicksight,
  ): CfnDataSet {
    return new CfnDataSet(this, "AddonsDataSet", {
      dataSetId: `${resourcePrefix}-cluster-addons`,
      name: "EKS Addons",
      awsAccountId: `${accountId}`,
      importMode: "DIRECT_QUERY",
      physicalTableMap: {
        PhysicalTable1: {
          customSql: {
            sqlQuery: `SELECT clustername AS eksClusterName,
                                          name        AS addonName,
                                          version     AS addonVersion,
                                          status      as addonStatus,
                                          accountid   AS accountId,
                                          region, date AS reportDate
                                   FROM "${props.databaseName}".singleton
                                   WHERE data = 'A'`,
            dataSourceArn: datasourceArn,
            name: "EKS-Addons-DS",
            columns: [
              {
                type: "STRING",
                name: "eksClusterName",
              },
              {
                type: "STRING",
                name: "addonName",
              },
              {
                type: "STRING",
                name: "addonVersion",
              },
              {
                type: "STRING",
                name: "addonStatus",
              },
              {
                type: "STRING",
                name: "accountId",
              },
              {
                type: "STRING",
                name: "region",
              },
              {
                type: "STRING",
                name: "reportDate",
              },
            ],
          },
        },
      },
      logicalTableMap: {
        LogicalTable1: {
          alias: "EKS Addons",
          source: {
            physicalTableId: "PhysicalTable1",
          },
          dataTransforms: [
            {
              renameColumnOperation: {
                columnName: "eksClusterName",
                newColumnName: "Cluster Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "addonName",
                newColumnName: "Addon Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "addonVersion",
                newColumnName: "Addon Version",
              },
            },
            {
              renameColumnOperation: {
                columnName: "addonStatus",
                newColumnName: "Addon Status",
              },
            },
            {
              renameColumnOperation: {
                columnName: "accountId",
                newColumnName: "Account",
              },
            },
            {
              renameColumnOperation: {
                columnName: "region",
                newColumnName: "Region",
              },
            },
          ],
        },
      },
      permissions: [
        {
          principal: props.quickSightUserArn,
          actions: [
            "quicksight:UpdateDataSetPermissions",
            "quicksight:DescribeDataSet",
            "quicksight:DescribeDataSetPermissions",
            "quicksight:PassDataSet",
            "quicksight:DescribeIngestion",
            "quicksight:ListIngestions",
            "quicksight:UpdateDataSet",
            "quicksight:DeleteDataSet",
            "quicksight:CreateIngestion",
            "quicksight:CancelIngestion",
          ],
        },
      ],
    });
  }

  csrDataSet(
    accountId: string,
    resourcePrefix: string,
    datasourceArn: string,
    props: Quicksight,
  ): CfnDataSet {
    return new CfnDataSet(this, "CSRDataSet", {
      dataSetId: `${resourcePrefix}-cluster-csr`,
      name: "EKS Certificate Signing Requests",
      awsAccountId: `${accountId}`,
      importMode: "DIRECT_QUERY",
      physicalTableMap: {
        PhysicalTable1: {
          customSql: {
            sqlQuery: `SELECT clustername   AS eksClusterName,
                                          csrname       AS csrName,
                                          signername    AS signerName,
                                          currentstatus AS currentStatus,
                                          accountid     AS accountId,
                                          region, date AS reportDate
                                   FROM "${props.databaseName}".csr
                                   WHERE data = 'A'`,
            dataSourceArn: datasourceArn,
            name: "EKS-CSR-DS",
            columns: [
              {
                type: "STRING",
                name: "eksClusterName",
              },
              {
                type: "STRING",
                name: "csrName",
              },
              {
                type: "STRING",
                name: "signerName",
              },
              {
                type: "STRING",
                name: "currentStatus",
              },
              {
                type: "STRING",
                name: "accountId",
              },
              {
                type: "STRING",
                name: "region",
              },
              {
                type: "STRING",
                name: "reportDate",
              },
            ],
          },
        },
      },
      logicalTableMap: {
        LogicalTable1: {
          alias: "EKS CSR",
          source: {
            physicalTableId: "PhysicalTable1",
          },
          dataTransforms: [
            {
              renameColumnOperation: {
                columnName: "eksClusterName",
                newColumnName: "Cluster Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "csrName",
                newColumnName: "CSR Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "signerName",
                newColumnName: "Signer Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "currentStatus",
                newColumnName: "Current Status",
              },
            },
            {
              renameColumnOperation: {
                columnName: "accountId",
                newColumnName: "Account",
              },
            },
            {
              renameColumnOperation: {
                columnName: "region",
                newColumnName: "Region",
              },
            },
          ],
        },
      },
      permissions: [
        {
          principal: props.quickSightUserArn,
          actions: [
            "quicksight:UpdateDataSetPermissions",
            "quicksight:DescribeDataSet",
            "quicksight:DescribeDataSetPermissions",
            "quicksight:PassDataSet",
            "quicksight:DescribeIngestion",
            "quicksight:ListIngestions",
            "quicksight:UpdateDataSet",
            "quicksight:DeleteDataSet",
            "quicksight:CreateIngestion",
            "quicksight:CancelIngestion",
          ],
        },
      ],
    });
  }

  deprecatedApIsDataSet(
    accountId: string,
    resourcePrefix: string,
    datasourceArn: string,
    props: Quicksight,
  ): CfnDataSet {
    return new CfnDataSet(this, "DeprecatedAPIsDataSet", {
      dataSetId: `${resourcePrefix}-cluster-deprecated-apis`,
      name: "EKS Deprecated APIs",
      awsAccountId: `${accountId}`,
      importMode: "DIRECT_QUERY",
      physicalTableMap: {
        PhysicalTable1: {
          customSql: {
            sqlQuery: `SELECT clustername          AS eksClusterName,
                                          name                 AS apiName,
                                          apiversion           AS apiVersion,
                                          ruleset              AS ruleSet,
                                          replacewith          AS apiReplacement,
                                          sinceversion         AS deprecatedSince,
                                          stopversion          AS removedVersion,
                                          requestsinlast30days AS requestsInLast30Days,
                                          message,
                                          accountid            AS accountId,
                                          insightstatus        as status,
                                          region, date AS reportDate
                                   FROM "${props.databaseName}".deprecatedapis
                                   WHERE data = 'A'`,
            dataSourceArn: datasourceArn,
            name: "EKS-Deprecated-APIs-DS",
            columns: [
              {
                type: "STRING",
                name: "eksClusterName",
              },
              {
                type: "STRING",
                name: "apiName",
              },
              {
                type: "STRING",
                name: "apiVersion",
              },
              {
                type: "STRING",
                name: "ruleSet",
              },
              {
                type: "STRING",
                name: "apiReplacement",
              },
              {
                type: "STRING",
                name: "deprecatedSince",
              },
              {
                type: "STRING",
                name: "removedVersion",
              },
              {
                type: "INTEGER",
                name: "requestsInLast30Days",
              },
              {
                type: "STRING",
                name: "message",
              },
              {
                type: "STRING",
                name: "accountId",
              },
              {
                type: "STRING",
                name: "region",
              },
              {
                type: "STRING",
                name: "reportDate",
              },
              {
                type: "STRING",
                name: "status",
              },
            ],
          },
        },
      },
      logicalTableMap: {
        LogicalTable1: {
          alias: "EKS Deprecated APIs",
          source: {
            physicalTableId: "PhysicalTable1",
          },
          dataTransforms: [
            {
              renameColumnOperation: {
                columnName: "eksClusterName",
                newColumnName: "Cluster Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "apiName",
                newColumnName: "API Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "apiVersion",
                newColumnName: "API Version",
              },
            },
            {
              renameColumnOperation: {
                columnName: "ruleSet",
                newColumnName: "Ruleset",
              },
            },
            {
              renameColumnOperation: {
                columnName: "apiReplacement",
                newColumnName: "API Replacement",
              },
            },
            {
              renameColumnOperation: {
                columnName: "deprecatedSince",
                newColumnName: "Deprecated Since",
              },
            },
            {
              renameColumnOperation: {
                columnName: "removedVersion",
                newColumnName: "Removed In",
              },
            },
            {
              renameColumnOperation: {
                columnName: "requestsInLast30Days",
                newColumnName: "Last 30 Days Usage",
              },
            },
            {
              renameColumnOperation: {
                columnName: "message",
                newColumnName: "Recommendation",
              },
            },
            {
              renameColumnOperation: {
                columnName: "accountId",
                newColumnName: "Account",
              },
            },
            {
              renameColumnOperation: {
                columnName: "status",
                newColumnName: "Status",
              },
            },
            {
              renameColumnOperation: {
                columnName: "region",
                newColumnName: "Region",
              },
            },
          ],
        },
      },
      permissions: [
        {
          principal: props.quickSightUserArn,
          actions: [
            "quicksight:UpdateDataSetPermissions",
            "quicksight:DescribeDataSet",
            "quicksight:DescribeDataSetPermissions",
            "quicksight:PassDataSet",
            "quicksight:DescribeIngestion",
            "quicksight:ListIngestions",
            "quicksight:UpdateDataSet",
            "quicksight:DeleteDataSet",
            "quicksight:CreateIngestion",
            "quicksight:CancelIngestion",
          ],
        },
      ],
    });
  }

  metadataDataSet(
    accountId: string,
    resourcePrefix: string,
    datasourceArn: string,
    props: Quicksight,
  ): CfnDataSet {
    return new CfnDataSet(this, "MetadataDataSet", {
      dataSetId: `${resourcePrefix}-cluster-metadata`,
      name: "EKS Cluster Metadata",
      awsAccountId: `${accountId}`,
      importMode: "DIRECT_QUERY",
      physicalTableMap: {
        PhysicalTable1: {
          customSql: {
            sqlQuery: `SELECT clustername                    AS eksClusterName,
                                          kubectlversion                 AS clientVersion,
                                          clusterversion                 AS eksClusterVersion,
                                          addondetails_coredns_details   AS coreDnsDetails,
                                          addondetails_kubeproxy_details AS kubeProxyDetails,
                                          addondetails_awsnode_details   AS awsNodeDetails,
                                          totalworkernodes               AS totalWorkerNodes,
                                          accountid                      AS accountId,
                                          region, date AS reportDate
                                   FROM "${props.databaseName}".metadata`,
            dataSourceArn: datasourceArn,
            name: "EKS-Metadata-DS",
            columns: [
              {
                type: "STRING",
                name: "eksClusterName",
              },
              {
                type: "STRING",
                name: "clientVersion",
              },
              {
                type: "STRING",
                name: "eksClusterVersion",
              },
              {
                type: "STRING",
                name: "coreDnsDetails",
              },
              {
                type: "STRING",
                name: "kubeProxyDetails",
              },
              {
                type: "STRING",
                name: "awsNodeDetails",
              },
              {
                type: "INTEGER",
                name: "totalWorkerNodes",
              },
              {
                type: "STRING",
                name: "accountId",
              },
              {
                type: "STRING",
                name: "region",
              },
              {
                type: "STRING",
                name: "reportDate",
              },
            ],
          },
        },
      },
      logicalTableMap: {
        LogicalTable1: {
          alias: "EKS Cluster Metadata",
          source: {
            physicalTableId: "PhysicalTable1",
          },
          dataTransforms: [
            {
              renameColumnOperation: {
                columnName: "eksClusterName",
                newColumnName: "Cluster Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "eksClusterVersion",
                newColumnName: "Cluster Version",
              },
            },
            {
              renameColumnOperation: {
                columnName: "clientVersion",
                newColumnName: "Kubectl Version",
              },
            },
            {
              renameColumnOperation: {
                columnName: "coreDnsDetails",
                newColumnName: "CoreDns Addon Details",
              },
            },
            {
              renameColumnOperation: {
                columnName: "kubeProxyDetails",
                newColumnName: "KubeProxy Addon Details",
              },
            },
            {
              renameColumnOperation: {
                columnName: "awsNodeDetails",
                newColumnName: "AwsNode Addon Details",
              },
            },
            {
              renameColumnOperation: {
                columnName: "totalWorkerNodes",
                newColumnName: "Total Worker Nodes",
              },
            },
            {
              renameColumnOperation: {
                columnName: "accountId",
                newColumnName: "Account",
              },
            },
            {
              renameColumnOperation: {
                columnName: "region",
                newColumnName: "Region",
              },
            },
          ],
        },
      },
      permissions: [
        {
          principal: props.quickSightUserArn,
          actions: [
            "quicksight:UpdateDataSetPermissions",
            "quicksight:DescribeDataSet",
            "quicksight:DescribeDataSetPermissions",
            "quicksight:PassDataSet",
            "quicksight:DescribeIngestion",
            "quicksight:ListIngestions",
            "quicksight:UpdateDataSet",
            "quicksight:DeleteDataSet",
            "quicksight:CreateIngestion",
            "quicksight:CancelIngestion",
          ],
        },
      ],
    });
  }

  pspDataSet(
    accountId: string,
    resourcePrefix: string,
    datasourceArn: string,
    props: Quicksight,
  ): CfnDataSet {
    return new CfnDataSet(this, "PSPDataSet", {
      dataSetId: `${resourcePrefix}-cluster-psp`,
      name: "EKS Pod Security Policies",
      awsAccountId: `${accountId}`,
      importMode: "DIRECT_QUERY",
      physicalTableMap: {
        PhysicalTable1: {
          customSql: {
            sqlQuery: `SELECT clustername        AS eksClusterName,
                                          name               AS policyName,
                                          fsgroup            AS fsGroup,
                                          runasuser          AS runAsUser,
                                          supplementalgroups AS supplementalGroups,
                                          accountid          AS accountId,
                                          region, date AS reportDate
                                   FROM "${props.databaseName}".psp
                                   WHERE data = 'A'`,
            dataSourceArn: datasourceArn,
            name: "EKS-PSP-DS",
            columns: [
              {
                type: "STRING",
                name: "eksClusterName",
              },
              {
                type: "STRING",
                name: "policyName",
              },
              {
                type: "STRING",
                name: "fsGroup",
              },
              {
                type: "STRING",
                name: "runAsUser",
              },
              {
                type: "STRING",
                name: "supplementalGroups",
              },
              {
                type: "STRING",
                name: "accountId",
              },
              {
                type: "STRING",
                name: "region",
              },
              {
                type: "STRING",
                name: "reportDate",
              },
            ],
          },
        },
      },
      logicalTableMap: {
        LogicalTable1: {
          alias: "EKS PSP",
          source: {
            physicalTableId: "PhysicalTable1",
          },
          dataTransforms: [
            {
              renameColumnOperation: {
                columnName: "eksClusterName",
                newColumnName: "Cluster Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "policyName",
                newColumnName: "Policy Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "fsGroup",
                newColumnName: "FSGroup",
              },
            },
            {
              renameColumnOperation: {
                columnName: "runAsUser",
                newColumnName: "RunAsUser",
              },
            },
            {
              renameColumnOperation: {
                columnName: "supplementalGroups",
                newColumnName: "Supplemental Groups",
              },
            },
            {
              renameColumnOperation: {
                columnName: "accountId",
                newColumnName: "Account",
              },
            },
            {
              renameColumnOperation: {
                columnName: "region",
                newColumnName: "Region",
              },
            },
          ],
        },
      },
      permissions: [
        {
          principal: props.quickSightUserArn,
          actions: [
            "quicksight:UpdateDataSetPermissions",
            "quicksight:DescribeDataSet",
            "quicksight:DescribeDataSetPermissions",
            "quicksight:PassDataSet",
            "quicksight:DescribeIngestion",
            "quicksight:ListIngestions",
            "quicksight:UpdateDataSet",
            "quicksight:DeleteDataSet",
            "quicksight:CreateIngestion",
            "quicksight:CancelIngestion",
          ],
        },
      ],
    });
  }

  singletonResourcesDataSet(
    accountId: string,
    resourcePrefix: string,
    datasourceArn: string,
    props: Quicksight,
  ): CfnDataSet {
    return new CfnDataSet(this, "SingletonResourcesDataSet", {
      dataSetId: `${resourcePrefix}-cluster-singleton-resources`,
      name: "EKS Singleton Resources",
      awsAccountId: `${accountId}`,
      importMode: "DIRECT_QUERY",
      physicalTableMap: {
        PhysicalTable1: {
          customSql: {
            sqlQuery: `SELECT clustername AS eksClusterName,
                                          resource    AS resourceType,
                                          name,
                                          namespace   AS nameSpace,
                                          accountid   AS accountId,
                                          region, date AS reportDate
                                   FROM "${props.databaseName}".singleton
                                   WHERE data = 'A'`,
            dataSourceArn: datasourceArn,
            name: "EKS-Singleton-Resources-DS",
            columns: [
              {
                type: "STRING",
                name: "eksClusterName",
              },
              {
                type: "STRING",
                name: "resourceType",
              },
              {
                type: "STRING",
                name: "nameSpace",
              },
              {
                type: "STRING",
                name: "accountId",
              },
              {
                type: "STRING",
                name: "region",
              },
              {
                type: "STRING",
                name: "reportDate",
              },
            ],
          },
        },
      },
      logicalTableMap: {
        LogicalTable1: {
          alias: "EKS Singleton Resources",
          source: {
            physicalTableId: "PhysicalTable1",
          },
          dataTransforms: [
            {
              renameColumnOperation: {
                columnName: "eksClusterName",
                newColumnName: "Cluster Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "resourceType",
                newColumnName: "Resource Type",
              },
            },
            {
              renameColumnOperation: {
                columnName: "nameSpace",
                newColumnName: "Namespace",
              },
            },
            {
              renameColumnOperation: {
                columnName: "accountId",
                newColumnName: "Account",
              },
            },
            {
              renameColumnOperation: {
                columnName: "region",
                newColumnName: "Region",
              },
            },
          ],
        },
      },
      permissions: [
        {
          principal: props.quickSightUserArn,
          actions: [
            "quicksight:UpdateDataSetPermissions",
            "quicksight:DescribeDataSet",
            "quicksight:DescribeDataSetPermissions",
            "quicksight:PassDataSet",
            "quicksight:DescribeIngestion",
            "quicksight:ListIngestions",
            "quicksight:UpdateDataSet",
            "quicksight:DeleteDataSet",
            "quicksight:CreateIngestion",
            "quicksight:CancelIngestion",
          ],
        },
      ],
    });
  }

  unhealthyPodsDataSet(
    accountId: string,
    resourcePrefix: string,
    datasourceArn: string,
    props: Quicksight,
  ): CfnDataSet {
    return new CfnDataSet(this, "UnhealthyPodsDataSet", {
      dataSetId: `${resourcePrefix}-cluster-unhealthy-pods`,
      name: "EKS Unhealthy Pods",
      awsAccountId: `${accountId}`,
      importMode: "DIRECT_QUERY",
      physicalTableMap: {
        PhysicalTable1: {
          customSql: {
            sqlQuery: `SELECT clustername AS eksClusterName,
                                          namespace   AS nameSpace,
                                          podname     AS podName,
                                          podstatus   AS podStatus,
                                          errorreason AS errorReason,
                                          accountid   AS accountId,
                                          region, date AS reportDate
                                   FROM "${props.databaseName}".unhealthypods
                                   WHERE data = 'A'`,
            dataSourceArn: datasourceArn,
            name: "EKS-Unhealthy-Pods-DS",
            columns: [
              {
                type: "STRING",
                name: "eksClusterName",
              },
              {
                type: "STRING",
                name: "nameSpace",
              },
              {
                type: "STRING",
                name: "podName",
              },
              {
                type: "STRING",
                name: "podStatus",
              },
              {
                type: "STRING",
                name: "errorReason",
              },
              {
                type: "STRING",
                name: "accountId",
              },
              {
                type: "STRING",
                name: "region",
              },
              {
                type: "STRING",
                name: "reportDate",
              },
            ],
          },
        },
      },
      logicalTableMap: {
        LogicalTable1: {
          alias: "EKS Unhealthy Pods",
          source: {
            physicalTableId: "PhysicalTable1",
          },
          dataTransforms: [
            {
              renameColumnOperation: {
                columnName: "eksClusterName",
                newColumnName: "Cluster Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "nameSpace",
                newColumnName: "Namespace",
              },
            },
            {
              renameColumnOperation: {
                columnName: "podName",
                newColumnName: "Pod Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "podStatus",
                newColumnName: "Pod Status",
              },
            },
            {
              renameColumnOperation: {
                columnName: "errorReason",
                newColumnName: "Error Reason",
              },
            },
            {
              renameColumnOperation: {
                columnName: "accountId",
                newColumnName: "Account",
              },
            },
            {
              renameColumnOperation: {
                columnName: "region",
                newColumnName: "Region",
              },
            },
          ],
        },
      },
      permissions: [
        {
          principal: props.quickSightUserArn,
          actions: [
            "quicksight:UpdateDataSetPermissions",
            "quicksight:DescribeDataSet",
            "quicksight:DescribeDataSetPermissions",
            "quicksight:PassDataSet",
            "quicksight:DescribeIngestion",
            "quicksight:ListIngestions",
            "quicksight:UpdateDataSet",
            "quicksight:DeleteDataSet",
            "quicksight:CreateIngestion",
            "quicksight:CancelIngestion",
          ],
        },
      ],
    });
  }

  workerNodesDataSet(
    accountId: string,
    resourcePrefix: string,
    datasourceArn: string,
    props: Quicksight,
  ): CfnDataSet {
    return new CfnDataSet(this, "WorkerNodesDataSet", {
      dataSetId: `${resourcePrefix}-cluster-worker-nodes`,
      name: "EKS Cluster Worker Nodes",
      awsAccountId: `${accountId}`,
      importMode: "DIRECT_QUERY",
      physicalTableMap: {
        PhysicalTable1: {
          customSql: {
            sqlQuery: `SELECT clustername    AS eksClusterName,
                                          name,
                                          kubeletversion AS kubeletVersion,
                                          accountid      AS accountId,
                                          region, date AS reportDate
                                   FROM "${props.databaseName}".workernodes
                                   WHERE data = 'A'`,
            dataSourceArn: datasourceArn,
            name: "EKS-Worker-Nodes-DS",
            columns: [
              {
                type: "STRING",
                name: "eksClusterName",
              },
              {
                type: "STRING",
                name: "kubeletVersion",
              },
              {
                type: "STRING",
                name: "accountId",
              },
              {
                type: "STRING",
                name: "region",
              },
              {
                type: "STRING",
                name: "reportDate",
              },
            ],
          },
        },
      },
      logicalTableMap: {
        LogicalTable1: {
          alias: "EKS Cluster WorkerNodes",
          source: {
            physicalTableId: "PhysicalTable1",
          },
          dataTransforms: [
            {
              renameColumnOperation: {
                columnName: "eksClusterName",
                newColumnName: "Cluster Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "kubeletVersion",
                newColumnName: "Kubelet Version",
              },
            },
            {
              renameColumnOperation: {
                columnName: "accountId",
                newColumnName: "Account",
              },
            },
            {
              renameColumnOperation: {
                columnName: "region",
                newColumnName: "Region",
              },
            },
          ],
        },
      },
      permissions: [
        {
          principal: props.quickSightUserArn,
          actions: [
            "quicksight:UpdateDataSetPermissions",
            "quicksight:DescribeDataSet",
            "quicksight:DescribeDataSetPermissions",
            "quicksight:PassDataSet",
            "quicksight:DescribeIngestion",
            "quicksight:ListIngestions",
            "quicksight:UpdateDataSet",
            "quicksight:DeleteDataSet",
            "quicksight:CreateIngestion",
            "quicksight:CancelIngestion",
          ],
        },
      ],
    });
  }

  backupRestoreDataSet(
    accountId: string,
    resourcePrefix: string,
    datasourceArn: string,
    props: Quicksight,
  ): CfnDataSet {
    return new CfnDataSet(this, "BackupRestoreDataSet", {
      dataSetId: `${resourcePrefix}-cluster-backup-restore`,
      name: "EKS Cluster Backup and Restore",
      awsAccountId: `${accountId}`,
      importMode: "DIRECT_QUERY",
      physicalTableMap: {
        PhysicalTable1: {
          customSql: {
            sqlQuery: `SELECT clustername           AS eksClusterName,
                                          clusterversion        AS eksClusterVersion,
                                          podstatus             as podStatus,
                                          serviceaccount        AS serviceAccount,
                                          serviceaccountstatus  AS serviceAccountStatus,
                                          backupstatus          AS backupStatus,
                                          backupname            as backupName,
                                          backuplocation        as backupLocation,
                                          restorestatus         as restoreStatus,
                                          restorebackuplocation as restoreBackupLocation,
                                          accountid             AS accountId,
                                          region, date AS reportDate
                                   FROM "${props.databaseName}".backupandrestore`,
            dataSourceArn: datasourceArn,
            name: "EKS-Backup-Restore-DS",
            columns: [
              {
                type: "STRING",
                name: "eksClusterName",
              },
              {
                type: "STRING",
                name: "eksClusterVersion",
              },
              {
                type: "STRING",
                name: "podStatus",
              },
              {
                type: "STRING",
                name: "serviceAccount",
              },
              {
                type: "STRING",
                name: "serviceAccountStatus",
              },
              {
                type: "STRING",
                name: "backupStatus",
              },
              {
                type: "STRING",
                name: "backupName",
              },
              {
                type: "STRING",
                name: "backupLocation",
              },
              {
                type: "STRING",
                name: "restoreStatus",
              },
              {
                type: "STRING",
                name: "restoreBackupLocation",
              },
              {
                type: "STRING",
                name: "accountId",
              },
              {
                type: "STRING",
                name: "region",
              },
              {
                type: "STRING",
                name: "reportDate",
              },
            ],
          },
        },
      },
      logicalTableMap: {
        LogicalTable1: {
          alias: "EKS Cluster Backup and Restore",
          source: {
            physicalTableId: "PhysicalTable1",
          },
          dataTransforms: [
            {
              renameColumnOperation: {
                columnName: "eksClusterName",
                newColumnName: "Cluster Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "eksClusterVersion",
                newColumnName: "Cluster Version",
              },
            },
            {
              renameColumnOperation: {
                columnName: "podStatus",
                newColumnName: "Velero Pod Status",
              },
            },
            {
              renameColumnOperation: {
                columnName: "serviceAccount",
                newColumnName: "Velero Service Account",
              },
            },
            {
              renameColumnOperation: {
                columnName: "serviceAccountStatus",
                newColumnName: "Velero Service Account Status",
              },
            },
            {
              renameColumnOperation: {
                columnName: "backupStatus",
                newColumnName: "Velero Backup Status",
              },
            },
            {
              renameColumnOperation: {
                columnName: "backupName",
                newColumnName: "Velero Backup Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "backupLocation",
                newColumnName: "Velero Backup Location",
              },
            },
            {
              renameColumnOperation: {
                columnName: "restoreStatus",
                newColumnName: "Velero Restore Status",
              },
            },
            {
              renameColumnOperation: {
                columnName: "restoreBackupLocation",
                newColumnName: "Restored From Location",
              },
            },
            {
              renameColumnOperation: {
                columnName: "accountId",
                newColumnName: "Account",
              },
            },
            {
              renameColumnOperation: {
                columnName: "region",
                newColumnName: "Region",
              },
            },
          ],
        },
      },
      permissions: [
        {
          principal: props.quickSightUserArn,
          actions: [
            "quicksight:UpdateDataSetPermissions",
            "quicksight:DescribeDataSet",
            "quicksight:DescribeDataSetPermissions",
            "quicksight:PassDataSet",
            "quicksight:DescribeIngestion",
            "quicksight:ListIngestions",
            "quicksight:UpdateDataSet",
            "quicksight:DeleteDataSet",
            "quicksight:CreateIngestion",
            "quicksight:CancelIngestion",
          ],
        },
      ],
    });
  }

  addonUpgradeDataSet(
    accountId: string,
    resourcePrefix: string,
    datasourceArn: string,
    props: Quicksight,
  ): CfnDataSet {
    return new CfnDataSet(this, "AddonUpgradeDataSet", {
      dataSetId: `${resourcePrefix}-cluster-addon-upgrade`,
      name: "EKS Addon Upgrade",
      awsAccountId: `${accountId}`,
      importMode: "DIRECT_QUERY",
      physicalTableMap: {
        PhysicalTable1: {
          customSql: {
            sqlQuery: `SELECT clustername    AS eksClusterName,
                                          name           AS addonName,
                                          version,
                                          updatedversion AS upgradedVersion,
                                          updatestatus   AS upgradeStatus,
                                          message,
                                          accountid      AS accountId,
                                          region, date AS reportDate
                                   FROM "${props.databaseName}".addonsupgrade`,
            dataSourceArn: datasourceArn,
            name: "EKS-Addon-Upgrade-DS",
            columns: [
              {
                type: "STRING",
                name: "eksClusterName",
              },
              {
                type: "STRING",
                name: "addonName",
              },
              {
                type: "STRING",
                name: "upgradedVersion",
              },
              {
                type: "STRING",
                name: "upgradeStatus",
              },
              {
                type: "STRING",
                name: "message",
              },
              {
                type: "STRING",
                name: "accountId",
              },
              {
                type: "STRING",
                name: "region",
              },
              {
                type: "STRING",
                name: "reportDate",
              },
            ],
          },
        },
      },
      logicalTableMap: {
        LogicalTable1: {
          alias: "EKS Addon Upgrade",
          source: {
            physicalTableId: "PhysicalTable1",
          },
          dataTransforms: [
            {
              renameColumnOperation: {
                columnName: "eksClusterName",
                newColumnName: "Cluster Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "addonName",
                newColumnName: "Addon Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "upgradedVersion",
                newColumnName: "Upgraded Version",
              },
            },
            {
              renameColumnOperation: {
                columnName: "upgradeStatus",
                newColumnName: "Addon Upgrade status",
              },
            },
            {
              renameColumnOperation: {
                columnName: "accountId",
                newColumnName: "Account",
              },
            },
            {
              renameColumnOperation: {
                columnName: "region",
                newColumnName: "Region",
              },
            },
          ],
        },
      },
      permissions: [
        {
          principal: props.quickSightUserArn,
          actions: [
            "quicksight:UpdateDataSetPermissions",
            "quicksight:DescribeDataSet",
            "quicksight:DescribeDataSetPermissions",
            "quicksight:PassDataSet",
            "quicksight:DescribeIngestion",
            "quicksight:ListIngestions",
            "quicksight:UpdateDataSet",
            "quicksight:DeleteDataSet",
            "quicksight:CreateIngestion",
            "quicksight:CancelIngestion",
          ],
        },
      ],
    });
  }

  clusterUpgradeDataSet(
    accountId: string,
    resourcePrefix: string,
    datasourceArn: string,
    props: Quicksight,
  ): CfnDataSet {
    return new CfnDataSet(this, "ClusterUpgradeDataSet", {
      dataSetId: `${resourcePrefix}-cluster-upgrade`,
      name: "EKS Cluster Upgrade",
      awsAccountId: `${accountId}`,
      importMode: "DIRECT_QUERY",
      physicalTableMap: {
        PhysicalTable1: {
          customSql: {
            sqlQuery: `SELECT clustername               AS eksClusterName,
                                          clusterstatus             AS clusterStatus,
                                          clusterupdatestatus       AS clusterUpgradeStatus,
                                          postupgradeclusterversion AS upgradeClusterVersion,
                                          totalnodegroups           AS totalNodegroups,
                                          nodegroupsupdated         AS nodegroupsUpgraded,
                                          nodegroupsfailed          AS nodegroupsFailed,
                                          nodegroupsrunningdesired  AS nodegroupsRunningDesiredVersion,
                                          nodegroupsnotactive       AS nodegroupsNotActive,
                                          totaladdons               AS totalAddons,
                                          addonsupgraded            AS addonsUpgraded,
                                          addonsfailed              as addonsFailed,
                                          addonsnotactive           AS addonsNotActive,
                                          addonsnotsupported        AS addonsNotSupported,
                                          addonsnotininput          AS addonsNotInInput,
                                          addonsrunninglatest       AS addonsRunningDesiredVersion,
                                          message,
                                          accountid                 AS accountId,
                                          region, date AS reportDate
                                   FROM "${props.databaseName}".clustersupgrade`,
            dataSourceArn: datasourceArn,
            name: "EKS-Cluster-Upgrade-DS",
            columns: [
              {
                type: "STRING",
                name: "eksClusterName",
              },
              {
                type: "STRING",
                name: "clusterStatus",
              },
              {
                type: "STRING",
                name: "clusterUpgradeStatus",
              },
              {
                type: "STRING",
                name: "upgradedClusterVersion",
              },
              {
                type: "STRING",
                name: "totalNodegroups",
              },
              {
                type: "STRING",
                name: "nodegroupsUpgraded",
              },
              {
                type: "STRING",
                name: "nodegroupsFailed",
              },
              {
                type: "STRING",
                name: "nodegroupsRunningDesiredVersion",
              },
              {
                type: "STRING",
                name: "nodegroupsNotActive",
              },
              {
                type: "STRING",
                name: "totalAddons",
              },
              {
                type: "STRING",
                name: "addonsUpgraded",
              },
              {
                type: "STRING",
                name: "addonsFailed",
              },
              {
                type: "STRING",
                name: "addonsNotActive",
              },
              {
                type: "STRING",
                name: "addonsNotSupported",
              },
              {
                type: "STRING",
                name: "addonsNotInInput",
              },
              {
                type: "STRING",
                name: "addonsRunningDesiredVersion",
              },
              {
                type: "STRING",
                name: "message",
              },
              {
                type: "STRING",
                name: "accountId",
              },
              {
                type: "STRING",
                name: "region",
              },
              {
                type: "STRING",
                name: "reportDate",
              },
            ],
          },
        },
      },
      logicalTableMap: {
        LogicalTable1: {
          alias: "EKS Cluster Upgrade",
          source: {
            physicalTableId: "PhysicalTable1",
          },
          dataTransforms: [
            {
              renameColumnOperation: {
                columnName: "eksClusterName",
                newColumnName: "Cluster Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "clusterStatus",
                newColumnName: "Current EKS Cluster status",
              },
            },
            {
              renameColumnOperation: {
                columnName: "clusterUpgradeStatus",
                newColumnName: "EKS Cluster Upgrade status",
              },
            },
            {
              renameColumnOperation: {
                columnName: "upgradedClusterVersion",
                newColumnName: "EKS Cluster upgrade version",
              },
            },
            {
              renameColumnOperation: {
                columnName: "totalNodegroups",
                newColumnName: "Number of Nodegroups",
              },
            },
            {
              renameColumnOperation: {
                columnName: "nodegroupsUpgraded",
                newColumnName: "Upgraded Nodegroups",
              },
            },
            {
              renameColumnOperation: {
                columnName: "nodegroupsFailed",
                newColumnName: "Failed Nodegroups",
              },
            },
            {
              renameColumnOperation: {
                columnName: "nodegroupsRunningDesiredVersion",
                newColumnName: "No Action Required Nodegroups",
              },
            },
            {
              renameColumnOperation: {
                columnName: "nodegroupsNotActive",
                newColumnName: "Non Active Nodegroups",
              },
            },
            {
              renameColumnOperation: {
                columnName: "totalAddons",
                newColumnName: "Number of Addons",
              },
            },
            {
              renameColumnOperation: {
                columnName: "addonsUpgraded",
                newColumnName: "Upgraded Addons",
              },
            },
            {
              renameColumnOperation: {
                columnName: "addonsFailed",
                newColumnName: "Failed Addons",
              },
            },
            {
              renameColumnOperation: {
                columnName: "addonsNotActive",
                newColumnName: "Non Active Addons",
              },
            },
            {
              renameColumnOperation: {
                columnName: "addonsNotSupported",
                newColumnName: "Unsupported Addons",
              },
            },
            {
              renameColumnOperation: {
                columnName: "addonsNotInInput",
                newColumnName: "Addons not in Input",
              },
            },
            {
              renameColumnOperation: {
                columnName: "addonsRunningDesiredVersion",
                newColumnName: "No Action Required Addons",
              },
            },
            {
              renameColumnOperation: {
                columnName: "message",
                newColumnName: "Message",
              },
            },
            {
              renameColumnOperation: {
                columnName: "accountId",
                newColumnName: "Account",
              },
            },
            {
              renameColumnOperation: {
                columnName: "region",
                newColumnName: "Region",
              },
            },
          ],
        },
      },
      permissions: [
        {
          principal: props.quickSightUserArn,
          actions: [
            "quicksight:UpdateDataSetPermissions",
            "quicksight:DescribeDataSet",
            "quicksight:DescribeDataSetPermissions",
            "quicksight:PassDataSet",
            "quicksight:DescribeIngestion",
            "quicksight:ListIngestions",
            "quicksight:UpdateDataSet",
            "quicksight:DeleteDataSet",
            "quicksight:CreateIngestion",
            "quicksight:CancelIngestion",
          ],
        },
      ],
    });
  }

  nodegroupUpgradeDataSet(
    accountId: string,
    resourcePrefix: string,
    datasourceArn: string,
    props: Quicksight,
  ): CfnDataSet {
    return new CfnDataSet(this, "NodegroupUpgradeDataSet", {
      dataSetId: `${resourcePrefix}-cluster-nodegroup-upgrade`,
      name: "EKS Nodegroup Upgrade",
      awsAccountId: `${accountId}`,
      importMode: "DIRECT_QUERY",
      physicalTableMap: {
        PhysicalTable1: {
          customSql: {
            sqlQuery: `SELECT clustername    AS eksClusterName,
                                          name           AS nodegroupName,
                                          desiredversion AS desiredVersion,
                                          updatestatus   AS upgradeStatus,
                                          message,
                                          accountid      AS accountId,
                                          region, date AS reportDate
                                   FROM "${props.databaseName}".nodegroupsupgrade`,
            dataSourceArn: datasourceArn,
            name: "EKS-NodeGroup-Upgrade-DS",
            columns: [
              {
                type: "STRING",
                name: "eksClusterName",
              },
              {
                type: "STRING",
                name: "nodegroupName",
              },
              {
                type: "STRING",
                name: "desiredVersion",
              },
              {
                type: "STRING",
                name: "upgradeStatus",
              },
              {
                type: "STRING",
                name: "message",
              },
              {
                type: "STRING",
                name: "accountId",
              },
              {
                type: "STRING",
                name: "region",
              },
              {
                type: "STRING",
                name: "reportDate",
              },
            ],
          },
        },
      },
      logicalTableMap: {
        LogicalTable1: {
          alias: "EKS Nodegroup Upgrade",
          source: {
            physicalTableId: "PhysicalTable1",
          },
          dataTransforms: [
            {
              renameColumnOperation: {
                columnName: "eksClusterName",
                newColumnName: "Cluster Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "nodegroupName",
                newColumnName: "Nodegroup Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "desiredVersion",
                newColumnName: "Desired Upgrade Version",
              },
            },
            {
              renameColumnOperation: {
                columnName: "upgradeStatus",
                newColumnName: "Nodegroup Upgrade status",
              },
            },
            {
              renameColumnOperation: {
                columnName: "accountId",
                newColumnName: "Account",
              },
            },
            {
              renameColumnOperation: {
                columnName: "region",
                newColumnName: "Region",
              },
            },
          ],
        },
      },
      permissions: [
        {
          principal: props.quickSightUserArn,
          actions: [
            "quicksight:UpdateDataSetPermissions",
            "quicksight:DescribeDataSet",
            "quicksight:DescribeDataSetPermissions",
            "quicksight:PassDataSet",
            "quicksight:DescribeIngestion",
            "quicksight:ListIngestions",
            "quicksight:UpdateDataSet",
            "quicksight:DeleteDataSet",
            "quicksight:CreateIngestion",
            "quicksight:CancelIngestion",
          ],
        },
      ],
    });
  }

  postUpgradeDataSet(
    accountId: string,
    resourcePrefix: string,
    datasourceArn: string,
    props: Quicksight,
  ): CfnDataSet {
    return new CfnDataSet(this, "PostUpgradeDataSet", {
      dataSetId: `${resourcePrefix}-cluster-post-upgrade`,
      name: "EKS Post Upgrade",
      awsAccountId: `${accountId}`,
      importMode: "DIRECT_QUERY",
      physicalTableMap: {
        PhysicalTable1: {
          customSql: {
            sqlQuery: `SELECT clustername           AS eksClusterName,
                                          currentclusterversion AS currentClusterVersion,
                                          type,
                                          name,
                                          currentversion        AS currentVersion,
                                          status,
                                          message,
                                          accountid             AS accountId,
                                          region, date AS reportDate
                                   FROM "${props.databaseName}".postupgrade`,
            dataSourceArn: datasourceArn,
            name: "EKS-Addon-Upgrade-DS",
            columns: [
              {
                type: "STRING",
                name: "eksClusterName",
              },
              {
                type: "STRING",
                name: "currentClusterVersion",
              },
              {
                type: "STRING",
                name: "type",
              },
              {
                type: "STRING",
                name: "name",
              },
              {
                type: "STRING",
                name: "currentVersion",
              },
              {
                type: "STRING",
                name: "status",
              },
              {
                type: "STRING",
                name: "message",
              },
              {
                type: "STRING",
                name: "accountId",
              },
              {
                type: "STRING",
                name: "region",
              },
              {
                type: "STRING",
                name: "reportDate",
              },
            ],
          },
        },
      },
      logicalTableMap: {
        LogicalTable1: {
          alias: "EKS Post Upgrade",
          source: {
            physicalTableId: "PhysicalTable1",
          },
          dataTransforms: [
            {
              renameColumnOperation: {
                columnName: "eksClusterName",
                newColumnName: "Cluster Name",
              },
            },
            {
              renameColumnOperation: {
                columnName: "currentClusterVersion",
                newColumnName: "Current EKS Version",
              },
            },
            {
              renameColumnOperation: {
                columnName: "type",
                newColumnName: "Type of resource",
              },
            },
            {
              renameColumnOperation: {
                columnName: "name",
                newColumnName: "Name of resource",
              },
            },
            {
              renameColumnOperation: {
                columnName: "status",
                newColumnName: "Status of resource",
              },
            },
            {
              renameColumnOperation: {
                columnName: "message",
                newColumnName: "Message",
              },
            },
            {
              renameColumnOperation: {
                columnName: "accountId",
                newColumnName: "Account",
              },
            },
            {
              renameColumnOperation: {
                columnName: "region",
                newColumnName: "Region",
              },
            },
          ],
        },
      },
      permissions: [
        {
          principal: props.quickSightUserArn,
          actions: [
            "quicksight:UpdateDataSetPermissions",
            "quicksight:DescribeDataSet",
            "quicksight:DescribeDataSetPermissions",
            "quicksight:PassDataSet",
            "quicksight:DescribeIngestion",
            "quicksight:ListIngestions",
            "quicksight:UpdateDataSet",
            "quicksight:DeleteDataSet",
            "quicksight:CreateIngestion",
            "quicksight:CancelIngestion",
          ],
        },
      ],
    });
  }
}
