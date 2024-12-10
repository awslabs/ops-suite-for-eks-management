import { Backup } from "../../config/OrchestratorConfig";
import { Construct } from "constructs";
import {
  Code,
  Function,
  ILayerVersion,
  LayerVersion,
  Runtime,
} from "aws-cdk-lib/aws-lambda";
import path from "path";
import { PolicyStatement, Role, ServicePrincipal } from "aws-cdk-lib/aws-iam";
import { Duration, Fn } from "aws-cdk-lib";
import {
  AutomationDocument,
  AwsApiStep,
  AwsService,
  BranchStep,
  Choice,
  DataTypeEnum,
  DocumentFormat,
  HardCodedString,
  HardCodedStringMap,
  Input,
  OnFailure,
  Operation,
  StringVariable,
} from "@cdklabs/cdk-ssm-documents";
import { KubernetesVersion } from "aws-cdk-lib/aws-eks";
import { RunCommandStep } from "@cdklabs/cdk-ssm-documents/lib/parent-steps/automation/run-command-step";
import { StringMapVariable } from "@cdklabs/cdk-ssm-documents/lib/interface/variables/string-map-variable";
import { StringListVariable } from "@cdklabs/cdk-ssm-documents/lib/interface/variables/string-list-variable";
import { IBucket } from "aws-cdk-lib/aws-s3";
import { BucketDeployment, Source } from "aws-cdk-lib/aws-s3-deployment";

export interface BackupConstructProps {
  readonly config: Backup;
  readonly s3Bucket: IBucket;
}

export class BackupConstruct extends Construct {
  public function: Function;
  public role: Role;

  constructor(
    scope: Construct,
    id: string,
    resourcePrefix: string,
    props: BackupConstructProps,
  ) {
    super(scope, id);

    const accountId: string = Fn.sub("${AWS::AccountId}");
    const region: string = Fn.sub("${AWS::Region}");
    const defaultedProps: BackupConstructProps = this.defaults(
      resourcePrefix,
      region,
      props,
    );
    this.resources(accountId, region, resourcePrefix, defaultedProps);
  }

  defaults(
    resourcePrefix: string,
    region: string,
    props: BackupConstructProps,
  ): BackupConstructProps {
    const properties: BackupConstructProps = props;

    // Defaulting ssm automation document name
    const defaultDocName: string = `${resourcePrefix}-backup-runbook`;
    properties.config.documentName =
      props.config.documentName || defaultDocName;

    // Defaulting ssm automation cw log
    const defaultLogGroupName = `/aws/ssm/${properties.config.documentName}`;
    properties.config.cloudWatchLogGroupName =
      props.config.cloudWatchLogGroupName || defaultLogGroupName;
    properties.config.enableSSMCloudWatchLogsInTarget =
      props.config.enableSSMCloudWatchLogsInTarget || "true";

    // Defaulting lambda role name
    const defaultRoleName: string = `${resourcePrefix}-${region}-backup-lambda-role`;
    properties.config.roleName = props.config.roleName || defaultRoleName;

    // Defaulting lambda name
    const defaultName: string = `${resourcePrefix}-backup-automation-function`;
    properties.config.functionName = props.config.functionName || defaultName;

    // Defaulting velero version
    const defaultVeleroVersion: string = "v1.14.1";
    properties.config.veleroVersion =
      props.config.veleroVersion || defaultVeleroVersion;

    return properties;
  }

  resources(
    accountId: string,
    region: string,
    resourcePrefix: string,
    props: BackupConstructProps,
  ) {
    const backup: Backup = props.config;

    if (backup.enabled) {
      this.automationDocument(resourcePrefix, backup);
      this.role = this.lambdaRole(accountId, region, backup);
      this.function = this.lambdaFunction(resourcePrefix, props);
      this.uploadScriptsFolder(props.s3Bucket);
    }
  }

  automationDocument(
    resourcePrefix: string,
    props: Backup,
  ): AutomationDocument {
    const ssmDocument: AutomationDocument = new AutomationDocument(
      this,
      "BackupAutomationRunbook",
      {
        documentFormat: DocumentFormat.YAML,
        documentName: props.documentName,
        description: "Backup Automation runbook",
        updateMethod: "NewVersion",
        targetType: "/AWS::EC2::Instance",
        assumeRole: StringVariable.of("AssumeRole"),
        docInputs: [
          Input.ofTypeString("AssumeRole", {
            description: ` (Required) IAM Role ARN needed to run the Automation on the EC2 instance.
                                    Please refer > https://docs.aws.amazon.com/systems-manager/latest/userguide/automation-setup-iam.html for more information`,
          }),
          Input.ofTypeString("WorkingDirectory", {
            description:
              "(Optional) The working directory where summary scripts will be downloaded. Defaulted to /home/ec2-user/{resourcePrefix}",
            defaultValue: `/home/ec2-user/${resourcePrefix}-backup`,
          }),
          Input.ofTypeString("S3Bucket", {
            description:
              "(Required) S3 Bucket to download summary scripts, put logs and reports.",
          }),
          Input.ofTypeString("S3OutputLogsPrefix", {
            description: "(Optional) S3 Bucket Prefix to put the logs.",
          }),
          Input.ofTypeStringMap("CloudWatchOutputEnabled", {
            description:
              "(Optional) Stream SSM Command logs to cloudwatch in target account.",
            defaultValue: {
              CloudWatchOutputEnabled: props.enableSSMCloudWatchLogsInTarget,
              CloudWatchLogGroupName: props.cloudWatchLogGroupName,
            },
          }),
          Input.ofTypeStringList("InstanceId", {
            description: "(Required) The EC2 Bastion instance id.",
          }),
          Input.ofTypeString("ExecutionTimeout", {
            description:
              " (Optional) The time in seconds for a command to complete before it is considered to have failed. Default is 5 hours. Maximum is 172800 (48 hours)",
            defaultValue: "18000",
          }),
          Input.ofTypeString("DesiredEKSVersion", {
            description:
              "(Optional) EKS cluster to check API deprecation against. Defaulted to latest version.",
            defaultValue: KubernetesVersion.V1_29.version,
          }),
          Input.ofTypeString("DownloadPath", {
            description:
              "(Optional) Path where scripts and reports folder will be created. Defaulted to backup.",
            defaultValue: "src",
          }),
          Input.ofTypeString("ScriptBasePath", {
            description:
              "(Optional) Scripts base path. Defaulted to eks-management/backup/scripts.",
            defaultValue: "{{DownloadPath}}/scripts",
          }),
          Input.ofTypeString("ReportBasePath", {
            description:
              "(Optional) Report base path. Defaulted to eks-management/backup/reports.",
            defaultValue: "{{DownloadPath}}/reports",
          }),
          Input.ofTypeString("StorageBucketPrefix", {
            description: "(Optional) S3 Bucket Prefix.",
            defaultValue: `${props.storageBucketPrefix}`,
          }),
          Input.ofTypeString("VeleroVersion", {
            description: "(Optional) Velero version.",
            defaultValue: `${props.veleroVersion}`,
          }),
          Input.ofTypeString("EKSClusters", {
            description: `
                        ---
                        (Required) An array of JSON objects with cluster details and the necessary actions to take.
                            * Each JSON object should have AccountId, Region, ClusterName and Action
                            * Allowed values for Action is BACKUP and RESTORE.
                            * For RESTORE action, BackupName is required.
                            * Clusters belonging to the specific account and region where the EC2 instance is present will be backed up.
                            * Example,
                              "[
                                {
                                  "AccountId": "123456789012",
                                  "Region": "us-east-1",
                                  "ClusterName": "my-dummy-cluster",
                                  "Action": "BACKUP"
                                },
                                {
                                  "AccountId": "987654321098",
                                  "Region": "ap-south-1",
                                  "ClusterName": "my-second-dummy-cluster",
                                  "Action": "RESTORE",
                                }
                              ]"
                    `,
          }),
        ],
      },
    );

    const getInstance: AwsApiStep = new AwsApiStep(this, "GetInstance", {
      name: "GetInstance",
      service: AwsService.SSM,
      pascalCaseApi: "DescribeInstanceInformation",
      apiParams: {
        Filters: [
          {
            Key: "InstanceIds",
            Values: [StringVariable.of(" InstanceId ")],
          },
          {
            Key: "PingStatus",
            Values: ["Online"],
          },
        ],
      },
      description:
        "Get the Platform information about the bastion host. Only linux platforms are supported.",
      onFailure: OnFailure.abort(),
      maxAttempts: 1,
      outputs: [
        {
          outputType: DataTypeEnum.STRING,
          name: "instanceId",
          selector: "$.InstanceInformationList[0].InstanceId",
        },
        {
          outputType: DataTypeEnum.STRING,
          name: "platform",
          selector: "$.InstanceInformationList[0].PlatformName",
        },
      ],
    });

    const setup: RunCommandStep = new RunCommandStep(this, "Setup", {
      name: "Setup",
      description: `
                ---
                 In this step, the following tasks will be performed.
                    * Delete any existing directories and create them anew.
                    * Download the eks-backup scripts from the specified bucket.
                    * Install the necessary software if not already installed.
            `,
      documentName: HardCodedString.of("AWS-RunShellScript"),
      outputS3BucketName: StringVariable.of("S3Bucket"),
      outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
      cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
      parameters: HardCodedStringMap.of({
        commands: [
          "#!/bin/bash",
          "echo creating {{WorkingDirectory}} folder if not present",
          "main_directory={{WorkingDirectory}}",
          "mkdir -p $main_directory",
          "mkdir -p $lib_directory",
          "echo Creating config folder",
          "config_directory={{WorkingDirectory}}/config",
          "mkdir -p $config_directory",
          "echo Creating summary folder",
          "directory={{WorkingDirectory}}/{{DownloadPath}}",
          "rm -f -r $directory 2>/dev/null && mkdir $directory",
          "echo creating $directory/lib folder if not present",
          "lib_directory=$directory/lib",
          "echo Creating scripts and reports folders under backup folder",
          "mkdir {{WorkingDirectory}}/{{ScriptBasePath}} && mkdir {{WorkingDirectory}}/{{ReportBasePath}}",
          "echo Copying script library to local directory",
          "aws s3 cp s3://{{S3Bucket}}/scripts/lib $lib_directory --recursive || exit 1",
          "echo Copying scripts to local directory",
          "aws s3 cp s3://{{S3Bucket}}/scripts/backup {{WorkingDirectory}}/{{ScriptBasePath}} --recursive || exit 1",
          "echo Running software installation",
          "cd {{WorkingDirectory}}/{{ScriptBasePath}}",
          "sh setup/install.sh {{VeleroVersion}} || exit 1",
          "pip3 install -r setup/requirements.txt || exit 1",
        ],
        executionTimeout: StringVariable.of("ExecutionTimeout"),
      }),
      targets: StringListVariable.of("InstanceId"),
      onFailure: OnFailure.abort(),
      maxAttempts: 1,
    });

    const platformCheck: BranchStep = new BranchStep(this, "PlatformCheck", {
      name: "PlatformCheck",
      description: `
                ---
                Check if the bastion host is running the supported operating systems. Supported OS are
                    * Amazon Linux
            `,
      onFailure: OnFailure.abort(),
      maxAttempts: 1,
      isEnd: true,
      choices: [
        new Choice({
          operation: Operation.CONTAINS,
          constant: "Amazon Linux",
          variable: StringVariable.of("GetInstance.platform"),
          jumpToStepName: setup.name,
        }),
      ],
    });

    const getClusters: RunCommandStep = new RunCommandStep(
      this,
      "GetEKSClusters",
      {
        name: "GetEKSClusters",
        description: `
                ---
                In this step, the below tasks will be performed.
                    * Get the region where the instance is present and store it in region.txt
                    * Get all the EKS Clusters and store them in a clusters.json
            `,
        documentName: HardCodedString.of("AWS-RunShellScript"),
        outputS3BucketName: StringVariable.of("S3Bucket"),
        outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
        cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
        parameters: HardCodedStringMap.of({
          commands: [
            "echo fetching region",
            "cd {{WorkingDirectory}}",
            "python3 -m {{DownloadPath}}.scripts.region_config -d {{WorkingDirectory}} || exit 1",
            "cat {{WorkingDirectory}}/config/region.txt",
            "echo fetching clusters",
            "python3 -m {{DownloadPath}}.scripts.clusters_config -d {{WorkingDirectory}} || exit 1",
            "cat {{WorkingDirectory}}/config/clusters.json",
          ],
          executionTimeout: StringVariable.of("ExecutionTimeout"),
        }),
        targets: StringListVariable.of("InstanceId"),
        onFailure: OnFailure.abort(),
        maxAttempts: 1,
      },
    );

    const filterInputClusters: RunCommandStep = new RunCommandStep(
      this,
      "FilterInputClusters",
      {
        name: "FilterInputClusters",
        description: `
                ---
                Filter the input clusters based on the account and region.
            `,
        documentName: HardCodedString.of("AWS-RunShellScript"),
        outputS3BucketName: StringVariable.of("S3Bucket"),
        outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
        cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
        parameters: HardCodedStringMap.of({
          commands: [
            "cd {{WorkingDirectory}}",
            "echo Checking input clusters with the clusters present in the account",
            "python3 -m {{DownloadPath}}.scripts.filter_clusters_config -d {{WorkingDirectory}} \\",
            " -s {{ScriptBasePath}} -r {{ReportBasePath}} -i '{{EKSClusters}}' || exit 1",
          ],
          executionTimeout: StringVariable.of("ExecutionTimeout"),
        }),
        targets: StringListVariable.of("InstanceId"),
        onFailure: OnFailure.abort(),
        maxAttempts: 1,
      },
    );

    const kubeConfig: RunCommandStep = new RunCommandStep(this, "KubeConfig", {
      name: "KubeConfig",
      description: `
                ---
                In this step, the below tasks will be performed.
                    * Check if kubeconfig file exists
                    * Check if able to access the cluster
            `,
      documentName: HardCodedString.of("AWS-RunShellScript"),
      outputS3BucketName: StringVariable.of("S3Bucket"),
      outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
      cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
      parameters: HardCodedStringMap.of({
        commands: [
          "cd {{WorkingDirectory}}",
          "echo Checking kube configurations for the input clusters",
          "python3 -m {{DownloadPath}}.scripts.kube_config -d {{WorkingDirectory}} -s {{ScriptBasePath}} \\",
          "       -i '{{EKSClusters}}' || exit 1",
        ],
        executionTimeout: StringVariable.of("ExecutionTimeout"),
      }),
      targets: StringListVariable.of("InstanceId"),
      onFailure: OnFailure.abort(),
      maxAttempts: 1,
    });

    const inputClustersCheck: BranchStep = new BranchStep(
      this,
      "InputClustersCheck",
      {
        name: "InputClustersCheck",
        description: `
                ---
                Check if the account and region specific clusters are present in the input
            `,
        onFailure: OnFailure.abort(),
        maxAttempts: 1,
        isEnd: true,
        choices: [
          new Choice({
            operation: Operation.CONTAINS,
            constant: "EKS Clusters Found",
            variable: StringVariable.of("FilterInputClusters.Output"),
            jumpToStepName: kubeConfig.name,
          }),
        ],
      },
    );

    const configuration: RunCommandStep = new RunCommandStep(
      this,
      "Configuration",
      {
        name: "Configuration",
        description: `
                ---
                In this step, the below tasks will be performed.
                    * Delete all the existing reports for the clusters
                    * Create ClusterRoleBinding configuration YAML file which will be used to RBAC for the Service Account
                    * Create Service Account configuration file which will be used to create the Service Account in the cluster
                    * Create IAM Role trust relationship JSON file which be used to create IAM Role with S3 bucket access and
                        will be used while creating the Service Account in the EKS Cluster.
            `,
        documentName: HardCodedString.of("AWS-RunShellScript"),
        outputS3BucketName: StringVariable.of("S3Bucket"),
        outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
        cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
        parameters: HardCodedStringMap.of({
          commands: [
            "cd {{WorkingDirectory}}",
            "echo Cleaning existing reports and creating respective folders anew",
            "python3 -m {{DownloadPath}}.scripts.reports_config -d {{WorkingDirectory}} -r {{ReportBasePath}} \\",
            "       -i '{{EKSClusters}}' || exit 1",
            "echo Generate the Service Account Role Binding Yaml",
            "python3 -m {{DownloadPath}}.scripts.role_binding_config -d {{WorkingDirectory}} -s {{ScriptBasePath}} \\",
            "       -i '{{EKSClusters}}' || exit 1",
            "echo Generate the Service Account Resource Yaml",
            "python3 -m {{DownloadPath}}.scripts.service_account_config -d {{WorkingDirectory}} -s {{ScriptBasePath}} \\",
            "       -i '{{EKSClusters}}' || exit 1",
            "echo Generate the Trust relationship for Service Account",
            "python3 -m {{DownloadPath}}.scripts.service_account_role_config -d {{WorkingDirectory}} -s {{ScriptBasePath}} \\",
            "       -i '{{EKSClusters}}' || exit 1",
          ],
          executionTimeout: StringVariable.of("ExecutionTimeout"),
        }),
        targets: StringListVariable.of("InstanceId"),
        onFailure: OnFailure.abort(),
        maxAttempts: 1,
      },
    );

    const serviceAccount: RunCommandStep = new RunCommandStep(
      this,
      "ServiceAccount",
      {
        name: "ServiceAccount",
        description: `
                ---
                In this step,
                    * Service Account with needed permissions will be created for each cluster and the specified namespace.
                    * The created service account will be bound to the to kubernetes ClusterRole
                    * eksctl will be used to create the service account.
            `,
        documentName: HardCodedString.of("AWS-RunShellScript"),
        outputS3BucketName: StringVariable.of("S3Bucket"),
        outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
        cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
        parameters: HardCodedStringMap.of({
          commands: [
            "cd {{WorkingDirectory}}",
            "python3 -m {{DownloadPath}}.scripts.service_account -d {{WorkingDirectory}} \\",
            "                   -s {{ScriptBasePath}} -r {{ReportBasePath}} -b {{S3Bucket}} \\",
            "                   -p {{StorageBucketPrefix}} -i '{{EKSClusters}}' || exit 1",
          ],
          executionTimeout: StringVariable.of("ExecutionTimeout"),
        }),
        targets: StringListVariable.of("InstanceId"),
        onFailure: OnFailure.abort(),
        maxAttempts: 1,
      },
    );

    const veleroInstall: RunCommandStep = new RunCommandStep(
      this,
      "VeleroInstall",
      {
        name: "VeleroInstall",
        description: `
                ---
                In this step,
                    * Service Account with needed permissions will be created for each cluster and the specified namespace.
                    * The created service account will be bound to the to kubernetes ClusterRole
                    * eksctl will be used to create the service account.
            `,
        documentName: HardCodedString.of("AWS-RunShellScript"),
        outputS3BucketName: StringVariable.of("S3Bucket"),
        outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
        cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
        parameters: HardCodedStringMap.of({
          commands: [
            "cd {{WorkingDirectory}}",
            "python3 -m {{DownloadPath}}.scripts.install_velero -d {{WorkingDirectory}} -s {{ScriptBasePath}} \\",
            "         -r {{ReportBasePath}} -b {{S3Bucket}} \\",
            "         -p {{StorageBucketPrefix}} -i '{{EKSClusters}}' || exit 1",
          ],
          executionTimeout: StringVariable.of("ExecutionTimeout"),
        }),
        targets: StringListVariable.of("InstanceId"),
        onFailure: OnFailure.abort(),
        maxAttempts: 1,
      },
    );

    const createBackup: RunCommandStep = new RunCommandStep(
      this,
      "CreateBackup",
      {
        name: "CreateBackup",
        description: `
                ---
                In this step,
                    * velero plugin will be installed in the cluster if it is not already installed.
                    * Backup resource will be deployed in all the clusters using the yaml files generated using Configuration.
            `,
        documentName: HardCodedString.of("AWS-RunShellScript"),
        outputS3BucketName: StringVariable.of("S3Bucket"),
        outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
        cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
        parameters: HardCodedStringMap.of({
          commands: [
            "cd {{WorkingDirectory}}",
            "python3 -m {{DownloadPath}}.scripts.velero_backup -d {{WorkingDirectory}} -s {{ScriptBasePath}} \\",
            "         -r {{ReportBasePath}} -b {{S3Bucket}} \\",
            "       -p {{StorageBucketPrefix}} -i '{{EKSClusters}}' || exit 1",
          ],
          executionTimeout: StringVariable.of("ExecutionTimeout"),
        }),
        targets: StringListVariable.of("InstanceId"),
        onFailure: OnFailure.abort(),
        maxAttempts: 1,
      },
    );

    const restoreBackup: RunCommandStep = new RunCommandStep(
      this,
      "RestoreBackup",
      {
        name: "RestoreBackup",
        description: `
                ---
                In this step,
                    * Based on the input, the clusters will be restored to the backup resources
            `,
        documentName: HardCodedString.of("AWS-RunShellScript"),
        outputS3BucketName: StringVariable.of("S3Bucket"),
        outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
        cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
        parameters: HardCodedStringMap.of({
          commands: [
            "cd {{WorkingDirectory}}",
            "python3 -m {{DownloadPath}}.scripts.velero_restore -d {{WorkingDirectory}} -s {{ScriptBasePath}} \\",
            "         -r {{ReportBasePath}} -b {{S3Bucket}} \\",
            "         -p {{StorageBucketPrefix}} -i '{{EKSClusters}}' || exit 1",
          ],
          executionTimeout: StringVariable.of("ExecutionTimeout"),
        }),
        targets: StringListVariable.of("InstanceId"),
        onFailure: OnFailure.abort(),
        maxAttempts: 1,
      },
    );

    ssmDocument.addStep(getInstance);
    ssmDocument.addStep(platformCheck);
    ssmDocument.addStep(setup);
    ssmDocument.addStep(getClusters);
    ssmDocument.addStep(filterInputClusters);
    ssmDocument.addStep(inputClustersCheck);
    ssmDocument.addStep(kubeConfig);
    ssmDocument.addStep(configuration);
    ssmDocument.addStep(serviceAccount);
    ssmDocument.addStep(veleroInstall);
    ssmDocument.addStep(createBackup);
    ssmDocument.addStep(restoreBackup);

    return ssmDocument;
  }

  lambdaRole(accountId: string, region: string, props: Backup): Role {
    const role: Role = new Role(this, "BackupLambdaRole", {
      assumedBy: new ServicePrincipal("lambda.amazonaws.com"),
      roleName: props.roleName,
      description:
        "Allows Lambda to access DynamoDB table and Start SSM Automation",
    });

    role.addToPolicy(
      new PolicyStatement({
        actions: [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ],
        resources: [
          `arn:aws:logs:${region}:${accountId}:log-group:/aws/lambda/${props.functionName}:log-stream:*`,
          `arn:aws:logs:${region}:${accountId}:log-group:/aws/lambda/${props.functionName}`,
        ],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        actions: [
          "dynamodb:BatchGetItem",
          "dynamodb:ConditionCheckItem",
          "dynamodb:GetItem",
          "dynamodb:Scan",
          "dynamodb:Query",
        ],
        resources: [
          `arn:aws:dynamodb:*:${accountId}:table/${props.tableName}`,
          `arn:aws:dynamodb:*:${accountId}:table/${props.tableName}/index/*`,
        ],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        actions: ["iam:GetRole", "iam:PassRole"],
        resources: [`${props.ssmAdminRole}`],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        actions: [
          "ssm:GetAutomationExecution",
          "ssm:StartAutomationExecution",
          "ssm:StopAutomationExecution",
        ],
        resources: [
          `arn:aws:ssm:*:${accountId}:automation-definition/${props.documentName}:*`,
        ],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        actions: [
          "ssm:GetMaintenanceWindowExecution",
          "ssm:GetMaintenanceWindowExecutionTaskInvocation",
          "ssm:GetCommandInvocation",
        ],
        resources: ["*"],
      }),
    );

    return role;
  }

  lambdaFunction(
    resourcePrefix: string,
    props: BackupConstructProps,
  ): Function {
    const backupConfig: Backup = props.config;

    const powerToolsLayerARN: string = Fn.sub(
      "arn:aws:lambda:${AWS::Region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:68",
    );
    const powerToolsLayer: ILayerVersion = LayerVersion.fromLayerVersionArn(
      this,
      "AWSLambdaPowertoolsPythonV2",
      powerToolsLayerARN,
    );

    const customLayerArn: string = backupConfig.layerArn!;
    const customLayer: ILayerVersion = LayerVersion.fromLayerVersionArn(
      this,
      "CustomLayer",
      customLayerArn,
    );

    return new Function(this, "BackupHandler", {
      description:
        "Lambda function to start the EKS Backup Automation runbook.",
      functionName: backupConfig.functionName,
      runtime: Runtime.PYTHON_3_12,
      code: Code.fromAsset(path.join(__dirname, "../lambdas/backup")),
      handler: "lambda_function.lambda_handler",
      memorySize: 256,
      timeout: Duration.seconds(180),
      layers: [powerToolsLayer, customLayer],
      role: this.role,
      environment: {
        TARGETS_TABLE: backupConfig.tableName || "",
        DOCUMENT_NAME: backupConfig.documentName || "",
        S3_BUCKET: props.s3Bucket.bucketName || "",
        SSM_ASSUME_ROLE: backupConfig.ssmAdminRole || "",
        POWERTOOLS_LOGGER_LOG_EVENT: "true",
        POWERTOOLS_LOG_LEVEL: "INFO",
        RESOURCE_PREFIX: resourcePrefix,
      },
    });
  }

  uploadScriptsFolder(s3Bucket: IBucket) {
    new BucketDeployment(this, "UploadBackupFolder", {
      sources: [Source.asset(path.join(__dirname, "../scripts/backup"))],
      destinationBucket: s3Bucket,
      destinationKeyPrefix: "scripts/backup",
    });
  }
}
