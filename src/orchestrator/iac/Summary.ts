import { Summary } from "../../config/OrchestratorConfig";
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
import { RetentionDays } from "aws-cdk-lib/aws-logs";

export interface SummaryConstructProps {
  readonly config: Summary;
  readonly s3Bucket: IBucket;
}

export class SummaryConstruct extends Construct {
  public function: Function;
  public role: Role;

  constructor(
    scope: Construct,
    id: string,
    resourcePrefix: string,
    props: SummaryConstructProps,
  ) {
    super(scope, id);

    const accountId: string = Fn.sub("${AWS::AccountId}");
    const region: string = Fn.sub("${AWS::Region}");

    const defaultedProps: SummaryConstructProps = this.defaults(
      resourcePrefix,
      props,
      region,
    );
    this.resources(accountId, region, resourcePrefix, defaultedProps);
  }

  defaults(
    resourcePrefix: string,
    props: SummaryConstructProps,
    region: string,
  ): SummaryConstructProps {
    const properties: SummaryConstructProps = props;

    // Defaulting ssm automation document name
    const defaultDocName: string = `${resourcePrefix}-summary-runbook`;
    properties.config.documentName =
      props.config.documentName || defaultDocName;

    // Defaulting ssm automation cw log
    const defaultLogGroupName = `/aws/ssm/${properties.config.documentName}`;
    properties.config.cloudWatchLogGroupName =
      props.config.cloudWatchLogGroupName || defaultLogGroupName;
    properties.config.enableSSMCloudWatchLogsInTarget =
      props.config.enableSSMCloudWatchLogsInTarget || "true";

    // Defaulting lambda role name
    const defaultRoleName: string = `${resourcePrefix}-${region}-summary-lambda-role-${region}`;
    properties.config.roleName = props.config.roleName || defaultRoleName;

    // Defaulting lambda name
    const defaultName: string = `${resourcePrefix}-summary-automation-function`;
    properties.config.functionName = props.config.functionName || defaultName;
    return properties;
  }

  resources(
    accountId: string,
    region: string,
    resourcePrefix: string,
    props: SummaryConstructProps,
  ) {
    const summary: Summary = props.config;

    if (summary.enabled) {
      this.automationDocument(resourcePrefix, summary);
      this.role = this.lambdaRole(accountId, region, summary);
      this.function = this.lambdaFunction(props);
      this.uploadScriptsFolder(props.s3Bucket);
    }
  }

  automationDocument(
    resourcePrefix: string,
    props: Summary,
  ): AutomationDocument {
    const ssmDocument: AutomationDocument = new AutomationDocument(
      this,
      "SummaryAutomationRunbook",
      {
        documentFormat: DocumentFormat.YAML,
        documentName: props.documentName,
        description: "Summary Automation runbook",
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
            defaultValue: `/home/ec2-user/${resourcePrefix}-summary`,
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
              "(Optional) Path where scripts and reports folder will be created. Defaulted to src",
            defaultValue: "src",
          }),
          Input.ofTypeString("ScriptBasePath", {
            description:
              "(Optional) Scripts base path. Defaulted to eks-management/summary/scripts.",
            defaultValue: "{{DownloadPath}}/scripts",
          }),
          Input.ofTypeString("ReportBasePath", {
            description:
              "(Optional) Report base path. Defaulted to eks-management/summary/reports.",
            defaultValue: "{{DownloadPath}}/reports",
          }),
          Input.ofTypeString("EKSClusters", {
            description: `
                        ---
                        (Required) An array of JSON objects with cluster details and the necessary actions to take.
                            * Each JSON object should have AccountId, Region, ClusterName and Action
                            * Allowed values for Action is SUMMARY.
                            * Summary will be collected for clusters belonging to the specific account and region where the EC2 instance is present.
                            * Example,
                              "[
                                {
                                  "AccountId": "123456789012",
                                  "Region": "us-east-1",
                                  "ClusterName": "my-dummy-cluster",
                                  "Action": "SUMMARY"
                                },
                                {
                                  "AccountId": "987654321098",
                                  "Region": "ap-south-1",
                                  "ClusterName": "my-second-dummy-cluster",
                                  "Action": "SUMMARY",
                                }
                              ]"
                    `,
            defaultValue: "[]",
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
                    * Download the summary scripts from the specified bucket.
                    * Install the necessary software if not already installed.
                    * Install the necessary python libraries
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
          "echo Creating scripts and reports folders under summary folder",
          "mkdir {{WorkingDirectory}}/{{ScriptBasePath}} && mkdir {{WorkingDirectory}}/{{ReportBasePath}}",
          "echo Copying script library to local directory",
          "aws s3 cp s3://{{S3Bucket}}/scripts/lib $lib_directory --recursive || exit 1",
          "echo Copying scripts to local directory",
          "aws s3 cp s3://{{S3Bucket}}/scripts/summary {{WorkingDirectory}}/{{ScriptBasePath}} --recursive || exit 1",
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
                In this step, the below tasks will be performed which will act as metadata for following steps.
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

    const clusterMetadata: RunCommandStep = new RunCommandStep(
      this,
      "ClusterMetadata",
      {
        name: "ClusterMetadata",
        description: `
                ---
                Collect metadata about the clusters.`,
        documentName: HardCodedString.of("AWS-RunShellScript"),
        outputS3BucketName: StringVariable.of("S3Bucket"),
        outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
        cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
        parameters: HardCodedStringMap.of({
          commands: [
            "cd {{WorkingDirectory}}",
            "python3 -m {{DownloadPath}}.scripts.metadata -b {{S3Bucket}} -d {{WorkingDirectory}} \\",
            " -s {{ScriptBasePath}} -r {{ReportBasePath}} -i '{{EKSClusters}}' || exit 1",
          ],
          executionTimeout: StringVariable.of("ExecutionTimeout"),
        }),
        targets: StringListVariable.of("InstanceId"),
        onFailure: OnFailure.abort(),
        maxAttempts: 1,
      },
    );

    const deprecatedAPIs: RunCommandStep = new RunCommandStep(
      this,
      "DeprecatedAPIs",
      {
        name: "DeprecatedAPIs",
        description: `
                ---
                If there are API deprecations reported, adjust your application manifests to use the stable API versions
                OR report any specific items as safe to ignore for the upgrade.
            `,
        documentName: HardCodedString.of("AWS-RunShellScript"),
        outputS3BucketName: StringVariable.of("S3Bucket"),
        outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
        cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
        parameters: HardCodedStringMap.of({
          commands: [
            "cd {{WorkingDirectory}}",
            "python3 -m {{DownloadPath}}.scripts.deprecated_apis -b {{S3Bucket}} \\",
            "           -d {{WorkingDirectory}} -s {{ScriptBasePath}} -r {{ReportBasePath}} \\",
            "           -v {{DesiredEKSVersion}} -i '{{EKSClusters}}' || exit 1",
          ],
          executionTimeout: StringVariable.of("ExecutionTimeout"),
        }),
        targets: StringListVariable.of("InstanceId"),
        onFailure: OnFailure.abort(),
        maxAttempts: 1,
      },
    );

    const csr: RunCommandStep = new RunCommandStep(this, "CSR", {
      name: "CSR",
      description: `
                ---
                If any CSRs are pending approval, they need to be approved prior to the upgrade.`,
      documentName: HardCodedString.of("AWS-RunShellScript"),
      outputS3BucketName: StringVariable.of("S3Bucket"),
      outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
      cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
      parameters: HardCodedStringMap.of({
        commands: [
          "cd {{WorkingDirectory}}",
          "python3 -m {{DownloadPath}}.scripts.csr -b {{S3Bucket}} -d {{WorkingDirectory}} -s {{ScriptBasePath}} \\",
          "   -r {{ReportBasePath}} -i '{{EKSClusters}}' || exit 1",
        ],
        executionTimeout: StringVariable.of("ExecutionTimeout"),
      }),
      targets: StringListVariable.of("InstanceId"),
      onFailure: OnFailure.abort(),
      maxAttempts: 1,
    });

    const psp: RunCommandStep = new RunCommandStep(this, "PSP", {
      name: "PSP",
      description: `
                ---
                Get any PSPs.
                These Pod Security Policies (PSPs) will be removed in EKS 1.25.
                Ensure you have alternative controls in place such as the built-in Pod Security Admission
                or a third-party tool like Kyverno to acheive same level of pod security controls.`,
      documentName: HardCodedString.of("AWS-RunShellScript"),
      outputS3BucketName: StringVariable.of("S3Bucket"),
      outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
      cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
      parameters: HardCodedStringMap.of({
        commands: [
          "cd {{WorkingDirectory}}",
          "python3 -m {{DownloadPath}}.scripts.psp -b {{S3Bucket}} -d {{WorkingDirectory}} \\",
          "    -s {{ScriptBasePath}} -r {{ReportBasePath}} -i '{{EKSClusters}}' || exit 1",
        ],
        executionTimeout: StringVariable.of("ExecutionTimeout"),
      }),
      targets: StringListVariable.of("InstanceId"),
      onFailure: OnFailure.abort(),
      maxAttempts: 1,
    });

    const unhealthyPods: RunCommandStep = new RunCommandStep(
      this,
      "UnhealthyPods",
      {
        name: "UnhealthyPods",
        description: `
                ---
                Get the list of pods which are unhealthy in the cluster`,
        documentName: HardCodedString.of("AWS-RunShellScript"),
        outputS3BucketName: StringVariable.of("S3Bucket"),
        outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
        cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
        parameters: HardCodedStringMap.of({
          commands: [
            "cd {{WorkingDirectory}}",
            "python3 -m {{DownloadPath}}.scripts.unhealthy_pod -b {{S3Bucket}} -d {{WorkingDirectory}} \\",
            "    -s {{ScriptBasePath}} -r {{ReportBasePath}} -i '{{EKSClusters}}' || exit 1",
          ],
          executionTimeout: StringVariable.of("ExecutionTimeout"),
        }),
        targets: StringListVariable.of("InstanceId"),
        onFailure: OnFailure.abort(),
        maxAttempts: 1,
      },
    );

    const singleton: RunCommandStep = new RunCommandStep(this, "Singleton", {
      name: "Singleton",
      description: `
                ---
                This is a report of pods and deployments which have risks to zero downtime requirement
                or otherwise not following best practices for high availability.
                Review this list and remediate any critical applications for optimized availability.`,
      documentName: HardCodedString.of("AWS-RunShellScript"),
      outputS3BucketName: StringVariable.of("S3Bucket"),
      outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
      cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
      parameters: HardCodedStringMap.of({
        commands: [
          "cd {{WorkingDirectory}}",
          "python3 -m {{DownloadPath}}.scripts.singleton -b {{S3Bucket}} -d {{WorkingDirectory}} \\",
          "   -s {{ScriptBasePath}} -r {{ReportBasePath}} -i '{{EKSClusters}}' || exit 1",
        ],
        executionTimeout: StringVariable.of("ExecutionTimeout"),
      }),
      targets: StringListVariable.of("InstanceId"),
      onFailure: OnFailure.abort(),
      maxAttempts: 1,
    });

    const addon: RunCommandStep = new RunCommandStep(this, "Addon", {
      name: "Addon",
      description: `
                ---
                This is a report of addons attached to the clusters.`,
      documentName: HardCodedString.of("AWS-RunShellScript"),
      outputS3BucketName: StringVariable.of("S3Bucket"),
      outputS3KeyPrefix: StringVariable.of("S3OutputLogsPrefix"),
      cloudWatchOutputConfig: StringMapVariable.of("CloudWatchOutputEnabled"),
      parameters: HardCodedStringMap.of({
        commands: [
          "cd {{WorkingDirectory}}",
          "python3 -m {{DownloadPath}}.scripts.addons -b {{S3Bucket}} -d {{WorkingDirectory}} \\",
          "   -s {{ScriptBasePath}} -r {{ReportBasePath}} -i '{{EKSClusters}}' || exit 1",
        ],
        executionTimeout: StringVariable.of("ExecutionTimeout"),
      }),
      targets: StringListVariable.of("InstanceId"),
      onFailure: OnFailure.abort(),
      maxAttempts: 1,
    });

    ssmDocument.addStep(getInstance);
    ssmDocument.addStep(platformCheck);
    ssmDocument.addStep(setup);
    ssmDocument.addStep(getClusters);
    ssmDocument.addStep(filterInputClusters);
    ssmDocument.addStep(inputClustersCheck);
    ssmDocument.addStep(kubeConfig);
    ssmDocument.addStep(preReportGeneration);
    ssmDocument.addStep(clusterMetadata);
    ssmDocument.addStep(deprecatedAPIs);
    ssmDocument.addStep(csr);
    ssmDocument.addStep(psp);
    ssmDocument.addStep(unhealthyPods);
    ssmDocument.addStep(singleton);
    ssmDocument.addStep(addon);

    return ssmDocument;
  }

  lambdaRole(accountId: string, region: string, props: Summary): Role {
    const role: Role = new Role(this, "SummaryLambdaRole", {
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

  lambdaFunction(props: SummaryConstructProps): Function {
    const summaryConfig: Summary = props.config;

    const powerToolsLayerARN: string = Fn.sub(
      "arn:aws:lambda:${AWS::Region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:68",
    );
    const powerToolsLayer: ILayerVersion = LayerVersion.fromLayerVersionArn(
      this,
      "AWSLambdaPowertoolsPythonV2",
      powerToolsLayerARN,
    );

    const customLayerArn: string = summaryConfig.layerArn!;
    const customLayer: ILayerVersion = LayerVersion.fromLayerVersionArn(
      this,
      "CustomLayer",
      customLayerArn,
    );

    return new Function(this, "SummaryHandler", {
      description:
        "Lambda function to start the EKS Summary Automation runbook.",
      functionName: summaryConfig.functionName,
      runtime: Runtime.PYTHON_3_12,
      code: Code.fromAsset(path.join(__dirname, "../lambdas/summary")),
      handler: "lambda_function.lambda_handler",
      memorySize: 256,
      timeout: Duration.seconds(180),
      layers: [powerToolsLayer, customLayer],
      role: this.role,
      environment: {
        TARGETS_TABLE: summaryConfig.tableName || "",
        DOCUMENT_NAME: summaryConfig.documentName || "",
        S3_BUCKET: props.s3Bucket.bucketName || "",
        SSM_ASSUME_ROLE: summaryConfig.ssmAdminRole || "",
        POWERTOOLS_LOGGER_LOG_EVENT: "true",
        POWERTOOLS_LOG_LEVEL: "INFO",
      },
      logRetention: RetentionDays.ONE_WEEK,
    });
  }

  uploadScriptsFolder(s3Bucket: IBucket) {
    new BucketDeployment(this, "UploadSummaryFolder", {
      sources: [Source.asset(path.join(__dirname, "../scripts/summary"))],
      destinationBucket: s3Bucket,
      destinationKeyPrefix: "scripts/summary",
    });
  }
}
