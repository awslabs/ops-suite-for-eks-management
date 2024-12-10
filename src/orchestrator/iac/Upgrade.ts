import { Upgrade } from "../../config/OrchestratorConfig";
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

export interface UpgradeConstructProps {
  readonly config: Upgrade;
  readonly s3Bucket: IBucket;
}

export class UpgradeConstruct extends Construct {
  public function: Function;
  public role: Role;

  constructor(
    scope: Construct,
    id: string,
    resourcePrefix: string,
    props: UpgradeConstructProps,
  ) {
    super(scope, id);

    const accountId: string = Fn.sub("${AWS::AccountId}");
    const region: string = Fn.sub("${AWS::Region}");

    const defaultedProps: UpgradeConstructProps = this.defaults(
      resourcePrefix,
      props,
      region,
    );
    this.resources(accountId, region, resourcePrefix, defaultedProps);
  }

  defaults(
    resourcePrefix: string,
    props: UpgradeConstructProps,
    region: string,
  ): UpgradeConstructProps {
    const properties: UpgradeConstructProps = props;

    // Defaulting ssm automation document name
    const defaultDocName: string = `${resourcePrefix}-upgrade-runbook`;
    properties.config.documentName =
      props.config.documentName || defaultDocName;

    // Defaulting ssm automation cw log
    const defaultLogGroupName = `/aws/ssm/${properties.config.documentName}`;
    properties.config.cloudWatchLogGroupName =
      props.config.cloudWatchLogGroupName || defaultLogGroupName;
    properties.config.enableSSMCloudWatchLogsInTarget =
      props.config.enableSSMCloudWatchLogsInTarget || "true";

    // Defaulting lambda role name
    const defaultRoleName: string = `${resourcePrefix}-${region}-upgrade-lambda-role-${region}`;
    properties.config.roleName = props.config.roleName || defaultRoleName;

    // Defaulting lambda name
    const defaultName: string = `${resourcePrefix}-upgrade-automation-function`;
    properties.config.functionName = props.config.functionName || defaultName;
    return properties;
  }

  resources(
    accountId: string,
    region: string,
    resourcePrefix: string,
    props: UpgradeConstructProps,
  ) {
    const upgrade: Upgrade = props.config;

    if (upgrade.enabled) {
      this.automationDocument(resourcePrefix, upgrade);
      this.role = this.lambdaRole(accountId, region, upgrade);
      this.function = this.lambdaFunction(props);

      this.uploadScriptsFolder(props.s3Bucket);
    }
  }

  automationDocument(
    resourcePrefix: string,
    props: Upgrade,
  ): AutomationDocument {
    const ssmDocument: AutomationDocument = new AutomationDocument(
      this,
      "UpgradeAutomationRunbook",
      {
        documentFormat: DocumentFormat.YAML,
        documentName: props.documentName,
        description: "Upgrade Automation runbook",
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
              "(Optional) The working directory where summary scripts will be downloaded. Defaulted to /home/ec2-user/eks-management",
            defaultValue: `/home/ec2-user/${resourcePrefix}-upgrade`,
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
              "(Optional) Path where scripts and reports folder will be created. Defaulted to upgrade.",
            defaultValue: "src",
          }),
          Input.ofTypeString("ScriptBasePath", {
            description:
              "(Optional) Scripts base path. Defaulted to eks-management/upgrade/scripts.",
            defaultValue: "{{DownloadPath}}/scripts",
          }),
          Input.ofTypeString("ReportBasePath", {
            description:
              "(Optional) Report base path. Defaulted to eks-management/upgrade/reports.",
            defaultValue: "{{DownloadPath}}/reports",
          }),
          Input.ofTypeString("UpdateSoftware", {
            description:
              "(Optional) Specify if kubectl, eksctl and kubent need to updated to the latest version. Defaulted to SKIP.",
            defaultValue: "SKIP",
            allowedValues: ["UPDATE", "SKIP"],
          }),
          Input.ofTypeString("EKSClusters", {
            description: `
                        ---
                        (Required) An array of JSON objects with cluster details.
                            * Each JSON object should have AccountId, Region, ClusterName and Action
                            * Clusters belonging to the specific account and region where the EC2 instance is present will be updated.
                            * Example,
                              "[
                                {
                                  "AccountId": "123456789012",
                                  "Region": "us-east-1",
                                  "ClusterName": "my-dummy-cluster"
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
                    * Download the eks-upgrade scripts from the specified bucket.
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
          "echo Creating scripts and reports folders under upgrade folder",
          "mkdir {{WorkingDirectory}}/{{ScriptBasePath}} && mkdir {{WorkingDirectory}}/{{ReportBasePath}}",
          "echo Copying script library to local directory",
          "aws s3 cp s3://{{S3Bucket}}/scripts/lib $lib_directory --recursive || exit 1",
          "echo Copying scripts to local directory",
          "aws s3 cp s3://{{S3Bucket}}/scripts/upgrade {{WorkingDirectory}}/{{ScriptBasePath}} --recursive || exit 1",
          "echo Running software installation",
          "cd {{WorkingDirectory}}/{{ScriptBasePath}}",
          "sh setup/install.sh $lib_directory || exit 1",
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

    const preReportGeneration: RunCommandStep = new RunCommandStep(
      this,
      "PreReportGeneration",
      {
        name: "PreReportGeneration",
        description: `
                ---
                In this step, the below tasks will be performed.
                    * Delete all the existing reports for the clusters
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
          ],
          executionTimeout: StringVariable.of("ExecutionTimeout"),
        }),
        targets: StringListVariable.of("InstanceId"),
        onFailure: OnFailure.abort(),
        maxAttempts: 1,
      },
    );

    const updateControlPlane: RunCommandStep = new RunCommandStep(
      this,
      "UpdateControlPlane",
      {
        name: "UpdateControlPlane",
        description: `
                ---
                In this step,
                    * The input clusters will be updated to the desired version using eksctl
            `,
        documentName: HardCodedString.of("AWS-RunShellScript"),
        outputS3BucketName: StringVariable.of("S3Bucket"),
        outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
        cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
        parameters: HardCodedStringMap.of({
          commands: [
            "cd {{WorkingDirectory}}",
            "python3 -m {{DownloadPath}}.scripts.upgrade_control_plane -d {{WorkingDirectory}} \\",
            "                   -s {{ScriptBasePath}} -r {{ReportBasePath}} -b {{S3Bucket}} \\",
            "                   -i '{{EKSClusters}}' || exit 1",
          ],
          executionTimeout: StringVariable.of("ExecutionTimeout"),
        }),
        targets: StringListVariable.of("InstanceId"),
        onFailure: OnFailure.abort(),
        maxAttempts: 1,
      },
    );

    const updateNodeGroups: RunCommandStep = new RunCommandStep(
      this,
      "UpdateNodeGroups",
      {
        name: "UpdateNodeGroups",
        description: `
                ---
                In this step,
                    * The managed node groups for the input clusters will be updated to the desired version using eksctl.
            `,
        documentName: HardCodedString.of("AWS-RunShellScript"),
        outputS3BucketName: StringVariable.of("S3Bucket"),
        outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
        cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
        parameters: HardCodedStringMap.of({
          commands: [
            "cd {{WorkingDirectory}}",
            "python3 -m {{DownloadPath}}.scripts.upgrade_nodes -d {{WorkingDirectory}} -s {{ScriptBasePath}} \\",
            "         -r {{ReportBasePath}} -b {{S3Bucket}} \\",
            "         -i '{{EKSClusters}}' || exit 1",
          ],
          executionTimeout: StringVariable.of("ExecutionTimeout"),
        }),
        targets: StringListVariable.of("InstanceId"),
        onFailure: OnFailure.abort(),
        maxAttempts: 1,
      },
    );

    const updateAddons: RunCommandStep = new RunCommandStep(
      this,
      "UpdateAddons",
      {
        name: "UpdateAddons",
        description: `
                ---
                In this step,
                    * The Amazon EKS Addons for the input clusters will be updated to the default version for
                        the desired EKS version using eksctl.
                    * \`vpc-cni\` and \`eks-pod-identity-agent\` addons will be updated to the next available minor version.
                    * Supported Addons are,
                        - \`vpc-cni\`
                        - \`coredns\`
                        - \`kube-proxy\`
                        - \`aws-ebs-csi-driver\`
                        - \`aws-efs-csi-driver\`
                        - \`snapshot-controller\`
                        - \`adot\`
                        - \`aws-guardduty-agent\`
                        - \`amazon-cloudwatch-observability\`
                        - \`eks-pod-identity-agent\`
                        - \`aws-mountpoint-s3-csi-driver\`
            `,
        documentName: HardCodedString.of("AWS-RunShellScript"),
        outputS3BucketName: StringVariable.of("S3Bucket"),
        outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
        cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
        parameters: HardCodedStringMap.of({
          commands: [
            "cd {{WorkingDirectory}}",
            "python3 -m {{DownloadPath}}.scripts.upgrade_addons -d {{WorkingDirectory}} -s {{ScriptBasePath}} \\",
            "         -r {{ReportBasePath}} -b {{S3Bucket}} -i '{{EKSClusters}}' || exit 1",
          ],
          executionTimeout: StringVariable.of("ExecutionTimeout"),
        }),
        targets: StringListVariable.of("InstanceId"),
        onFailure: OnFailure.abort(),
        maxAttempts: 1,
      },
    );

    const postClusterUpdate: RunCommandStep = new RunCommandStep(
      this,
      "PostClusterUpdate",
      {
        name: "PostClusterUpdate",
        description: `
                ---
                In this step,
                    * Post cluster report will be generated
            `,
        documentName: HardCodedString.of("AWS-RunShellScript"),
        outputS3BucketName: StringVariable.of("S3Bucket"),
        outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
        cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
        parameters: HardCodedStringMap.of({
          commands: [
            "cd {{WorkingDirectory}}",
            "python3 -m {{DownloadPath}}.scripts.post_upgrade -d {{WorkingDirectory}} -s {{ScriptBasePath}} \\",
            "         -r {{ReportBasePath}} -b {{S3Bucket}} -i '{{EKSClusters}}' || exit 1",
          ],
          executionTimeout: StringVariable.of("ExecutionTimeout"),
        }),
        targets: StringListVariable.of("InstanceId"),
        onFailure: OnFailure.abort(),
        maxAttempts: 1,
      },
    );

    const toolsUpdate: RunCommandStep = new RunCommandStep(
      this,
      "ToolsUpdate",
      {
        name: "ToolsUpdate",
        description: `
                ---
                In this step,
                    * kubectl
            `,
        documentName: HardCodedString.of("AWS-RunShellScript"),
        outputS3BucketName: StringVariable.of("S3Bucket"),
        outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
        cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
        parameters: HardCodedStringMap.of({
          commands: [
            "cd {{WorkingDirectory}}",
            "python3 -m {{DownloadPath}}.scripts.update_tools -d {{WorkingDirectory}} -s {{ScriptBasePath}} \\",
            "   -r {{ReportBasePath}} -b {{S3Bucket}} -i '{{EKSClusters}}' \\",
            "          -t {{UpdateSoftware}} || exit 1",
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
    ssmDocument.addStep(preReportGeneration);
    ssmDocument.addStep(updateControlPlane);
    ssmDocument.addStep(updateNodeGroups);
    ssmDocument.addStep(updateAddons);
    ssmDocument.addStep(postClusterUpdate);
    ssmDocument.addStep(toolsUpdate);

    return ssmDocument;
  }

  lambdaRole(accountId: string, region: string, props: Upgrade): Role {
    const role: Role = new Role(this, "UpgradeLambdaRole", {
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

  lambdaFunction(props: UpgradeConstructProps): Function {
    const upgradeConfig: Upgrade = props.config;

    const powerToolsLayerARN: string = Fn.sub(
      "arn:aws:lambda:${AWS::Region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:68",
    );
    const powerToolsLayer: ILayerVersion = LayerVersion.fromLayerVersionArn(
      this,
      "AWSLambdaPowertoolsPythonV2",
      powerToolsLayerARN,
    );

    const customLayerArn: string = upgradeConfig.layerArn!;
    const customLayer: ILayerVersion = LayerVersion.fromLayerVersionArn(
      this,
      "CustomLayer",
      customLayerArn,
    );

    return new Function(this, "UpgradeHandler", {
      description:
        "Lambda function to start the EKS Upgrade Automation runbook.",
      functionName: upgradeConfig.functionName,
      runtime: Runtime.PYTHON_3_12,
      code: Code.fromAsset(path.join(__dirname, "../lambdas/upgrade")),
      handler: "lambda_function.lambda_handler",
      memorySize: 256,
      timeout: Duration.seconds(180),
      layers: [powerToolsLayer, customLayer],
      role: this.role,
      environment: {
        TARGETS_TABLE: upgradeConfig.tableName || "",
        DOCUMENT_NAME: upgradeConfig.documentName || "",
        S3_BUCKET: props.s3Bucket.bucketName || "",
        SSM_ASSUME_ROLE: upgradeConfig.ssmAdminRole || "",
        POWERTOOLS_LOGGER_LOG_EVENT: "true",
        POWERTOOLS_LOG_LEVEL: "INFO",
      },
    });
  }

  uploadScriptsFolder(s3Bucket: IBucket) {
    new BucketDeployment(this, "UploadUpgradeFolder", {
      sources: [Source.asset(path.join(__dirname, "../scripts/upgrade"))],
      destinationBucket: s3Bucket,
      destinationKeyPrefix: "scripts/upgrade",
    });
  }
}
