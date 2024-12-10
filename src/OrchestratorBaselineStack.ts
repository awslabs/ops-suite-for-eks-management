import { OrchestratorConfig, Quicksight } from "./config/OrchestratorConfig";
import { Fn, Stack, StackProps } from "aws-cdk-lib";
import { Construct } from "constructs";
import { BaselineConstruct } from "./orchestrator/iac/Baseline";
import { SummaryConstruct } from "./orchestrator/iac/Summary";
import { MaintenanceWindowConstruct } from "./orchestrator/iac/MaintenanceWindow";
import { UpgradeConstruct } from "./orchestrator/iac/Upgrade";
import { BackupConstruct } from "./orchestrator/iac/Backup";
import { ReportGeneratorConstruct } from "./orchestrator/iac/ReportGenerator";
import { RestApiConstruct } from "./orchestrator/iac/RestApi";
import eks_orchestrator_quicksight_suppressions from "./orchestrator/eks-orchestrator-quicksight-suppressions.json";
import { QuicksightStack } from "./QuicksightStack";
import { NagSuppressions } from "cdk-nag";

export interface OrchestratorBaselineStackProps extends StackProps {
  readonly config: OrchestratorConfig;
  readonly resourcePrefix: string;
  readonly storageBucketPrefix: string;
}

export class OrchestratorBaselineStack extends Stack {
  constructor(
    scope: Construct,
    id: string,
    props: OrchestratorBaselineStackProps,
  ) {
    super(scope, id, props);
    let baseline: BaselineConstruct;
    let dynamoDBName: string = "";
    let summary = undefined;
    let backup = undefined;
    let upgrade = undefined;
    let reportGenerator = undefined;
    let restApi = undefined;
    let genAI = undefined;
    let quicksight = undefined;

    const resourcePrefix: string = props.resourcePrefix;
    baseline = new BaselineConstruct(this, "Baseline", resourcePrefix, {
      config: props.config.baseline,
    });

    const layerArn: string = baseline.layerArn;
    const s3BucketName: string = baseline.s3BucketName;
    const ssmAdminRole: string = baseline.ssmAdminRoleArn;
    const s3EventsQueueArn: string = baseline.s3EventsQueueArn;
    const s3EventsDlQueueArn: string = baseline.s3EventsDlQueueArn;
    dynamoDBName = baseline.tableName;

    const summaryEnabled: boolean = props.config.summary.enabled || false;
    const backupEnabled: boolean = props.config.backup.enabled || false;
    const upgradeEnabled: boolean = props.config.upgrade.enabled || false;

    if (summaryEnabled) {
      props.config.summary.layerArn = layerArn;
      props.config.summary.tableName = dynamoDBName;
      props.config.summary.ssmAdminRole = ssmAdminRole;

      summary = new SummaryConstruct(this, "Summary", resourcePrefix, {
        config: props.config.summary,
        s3Bucket: baseline.s3Bucket,
      });
      props.config.summary.maintenanceWindow.roleName = `${resourcePrefix}-summary-maintenance-task-role-${this.region}`;
      props.config.summary.maintenanceWindow.name = `${resourcePrefix}-summary-maintenance-window`;
      const summaryMaintenance = new MaintenanceWindowConstruct(
        this,
        "SummaryMaintenanceWindow",
        resourcePrefix,
        {
          config: props.config.summary.maintenanceWindow,
          lambdaFunction: summary.function,
        },
      );

      props.config.restApi.summaryFunction = summary.function.functionName;
    }

    if (backupEnabled) {
      props.config.backup.layerArn = layerArn;
      props.config.backup.tableName = dynamoDBName;
      props.config.backup.ssmAdminRole = ssmAdminRole;
      props.config.backup.storageBucketPrefix = props.storageBucketPrefix;

      backup = new BackupConstruct(this, "Backup", resourcePrefix, {
        config: props.config.backup,
        s3Bucket: baseline.s3Bucket,
      });
      props.config.backup.maintenanceWindow.roleName = `${resourcePrefix}-backup-maintenance-task-role-${this.region}`;
      props.config.backup.maintenanceWindow.name = `${resourcePrefix}-backup-maintenance-window`;
      const backupMaintenance = new MaintenanceWindowConstruct(
        this,
        "BackupMaintenanceWindow",
        resourcePrefix,
        {
          config: props.config.backup.maintenanceWindow,
          lambdaFunction: backup.function,
        },
      );

      props.config.restApi.backupFunction = backup.function.functionName;
    }

    if (upgradeEnabled) {
      props.config.upgrade.layerArn = layerArn;
      props.config.upgrade.tableName = dynamoDBName;
      props.config.upgrade.ssmAdminRole = ssmAdminRole;
      upgrade = new UpgradeConstruct(this, "Upgrade", resourcePrefix, {
        config: props.config.upgrade,
        s3Bucket: baseline.s3Bucket,
      });
      props.config.upgrade.maintenanceWindow.roleName = `${resourcePrefix}-upgrade-maintenance-task-role-${this.region}`;
      props.config.upgrade.maintenanceWindow.name = `${resourcePrefix}-upgrade-maintenance-window`;
      const upgradeMaintenance = new MaintenanceWindowConstruct(
        this,
        "UpgradeMaintenanceWindow",
        resourcePrefix,
        {
          config: props.config.upgrade.maintenanceWindow,
          lambdaFunction: upgrade.function,
        },
      );

      props.config.restApi.upgradeFunction = upgrade.function.functionName;
    }

    if (s3EventsQueueArn in [null, undefined]) {
      console.error(
        `${s3EventsQueueArn} not present. Please enable it to create it.`,
      );
      return;
    }

    if (s3EventsDlQueueArn in [null, undefined]) {
      console.error(
        `${s3EventsDlQueueArn} not present. Please enable it to create it.`,
      );
      return;
    }

    if (s3BucketName in [null, undefined]) {
      console.error(
        `${s3BucketName} not present. Please enable it to create it.`,
      );
      return;
    }

    props.config.reportGenerator.s3EventsQueueArn = s3EventsQueueArn;
    props.config.reportGenerator.s3EventsDlQueueArn = s3EventsDlQueueArn;
    props.config.reportGenerator.s3Bucket = s3BucketName;

    reportGenerator = new ReportGeneratorConstruct(
      this,
      "ReportGenerator",
      {
        config: props.config.reportGenerator,
      },
      resourcePrefix,
    );

    if (props.config.restApi.enabled) {
      props.config.restApi.layerArn = layerArn;
      props.config.restApi.glueDatabase = reportGenerator.glueDatabaseRef;
      props.config.restApi.athenaDataSource = reportGenerator.dataCatalogName;

      restApi = new RestApiConstruct(this, "RestApiGateway", resourcePrefix, {
        config: props.config.restApi,
        s3Bucket: baseline.s3Bucket,
        dynamodbTable: dynamoDBName,
        summaryEnabled: summaryEnabled,
        backupEnabled: backupEnabled,
        upgradeEnabled: upgradeEnabled,
      });
    }

    if (props.config.quicksight.enabled) {
      const quicksightProps: Quicksight = props.config.quicksight;
      if (quicksightProps.quickSightUserArn in [null, undefined]) {
        console.error(
          `${quicksightProps.quickSightUserArn} not present. Please provide.`,
        );
        return;
      }

      const summaryEnabled: boolean =
        props.config.quicksight.summary.enabled || false;
      const backupEnabled: boolean =
        props.config.quicksight.backup.enabled || false;
      const upgradeEnabled: boolean =
        props.config.quicksight.upgrade.enabled || false;

      quicksight = new QuicksightStack(
        scope,
        "eks-quicksight",
        resourcePrefix,
        {
          config: props.config.quicksight,
          s3BucketName,
          summaryEnabled,
          backupEnabled,
          upgradeEnabled,
        },
      );

      for (let suppression in eks_orchestrator_quicksight_suppressions) {
        NagSuppressions.addResourceSuppressionsByPath(
          quicksight,
          eks_orchestrator_quicksight_suppressions[suppression].path,
          eks_orchestrator_quicksight_suppressions[suppression].suppression,
        );
      }
    }
  }
}
