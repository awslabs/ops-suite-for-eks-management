import path from "path";
import { Baseline } from "../../config/OrchestratorConfig";
import { Construct } from "constructs";
import * as cdk from "aws-cdk-lib";
import { CfnOutput, Duration, Fn, RemovalPolicy } from "aws-cdk-lib";
import { PolicyStatement, Role, ServicePrincipal } from "aws-cdk-lib/aws-iam";
import { Code, LayerVersion, Runtime } from "aws-cdk-lib/aws-lambda";
import {
  BlockPublicAccess,
  Bucket,
  IBucket,
  StorageClass,
} from "aws-cdk-lib/aws-s3";
import { SqsDestination } from "aws-cdk-lib/aws-s3-notifications";
import { Queue, QueueEncryption } from "aws-cdk-lib/aws-sqs";
import { BucketDeployment, Source } from "aws-cdk-lib/aws-s3-deployment";

import { AttributeType, Table } from "aws-cdk-lib/aws-dynamodb";

export interface BaselineConstructProps {
  readonly config: Baseline;
}

export class BaselineConstruct extends Construct {
  DEFAULT_MAX_RECEIVE_COUNT: number = 10;
  DEFAULT_MESSAGE_RETENTION_IN_DAYS: number = 7;
  DEFAULT_MAX_MESSAGE_SIZE: number = 262144;
  DEFAULT_REPORTS_PREFIX: string = "reports/";
  DEFAULT_LOGS_PREFIX: string = "logs/";
  DEFAULT_EXPIRATION_FOR_ATHENA_QUERY: number = 10;
  DEFAULT_ATHENA_QUERY_PREFIX: string = "";
  DEFAULT_EXPIRATION_FOR_LOGS: number = 30;
  DEFAULT_EXPIRATION_FOR_REPORTS: number = 180;
  DEFAULT_TRANSITION_FOR_REPORTS: number = 30;
  DEFAULT_REPORTS_TRANSITION_CLASS: string =
    StorageClass.INTELLIGENT_TIERING.toString();
  /**
   * S3 Bucket name
   */
  public s3Bucket: IBucket;
  public s3BucketName: string;
  public ssmAdminRoleArn: string;
  public layerArn: string;
  public s3EventsQueueArn: string;
  public s3EventsDlQueueArn: string;
  public tableName: string;

  public defaultDLQueueName: string;
  public defaultQueueName: string;
  public ssmAdminRoleName: string;
  public defaultLayerName: string;

  constructor(
    scope: Construct,
    id: string,
    resourcePrefix: string,
    props: BaselineConstructProps,
  ) {
    super(scope, id);
    const defaultedProps: BaselineConstructProps = this.defaults(
      resourcePrefix,
      props,
    );
    this.resources(defaultedProps);
  }

  defaults(
    resourcePrefix: string,
    props: BaselineConstructProps,
  ): BaselineConstructProps {
    const properties: BaselineConstructProps = props;
    const accountId = Fn.sub("${AWS::AccountId}");
    const region = Fn.sub("${AWS::Region}");
    const roleSuffix: string = "SSMAutomationAdministrationRole";

    // Defaulting s3 bucket name
    this.s3BucketName = `${resourcePrefix.toLowerCase()}-${accountId}-${region}`;
    this.defaultDLQueueName = `${resourcePrefix}-dead-letter-queue`;
    this.defaultQueueName = `${resourcePrefix}-s3-events-queue`;
    this.ssmAdminRoleName = `${resourcePrefix}-${roleSuffix}-${region}`;
    this.defaultLayerName = `${resourcePrefix}-lambda-layer`;
    this.tableName = `${resourcePrefix}-tenant-accounts`;
    return properties;
  }

  resources(props: BaselineConstructProps) {
    // S3 Bucket Creation
    this.s3Bucket = this.s3CentralisedBucket();

    this.uploadScriptsLibFolder(this.s3Bucket);

    const sqsQueue: Queue = this.s3EventsQueue();

    new CfnOutput(this, "S3EventsQueueArn", {
      key: "S3EventsQueueArn",
      description: "ARN of the S3 events SQS",
      value: sqsQueue.queueArn,
    });

    this.s3Bucket.addObjectCreatedNotification(new SqsDestination(sqsQueue), {
      prefix: this.DEFAULT_REPORTS_PREFIX,
    });

    this.s3Bucket.addObjectRemovedNotification(new SqsDestination(sqsQueue), {
      prefix: this.DEFAULT_REPORTS_PREFIX,
    });

    const role: Role = this.ssmAdminRole();
    this.ssmAdminRoleArn = role.roleArn;
    new CfnOutput(this, "SSMAdminRoleArn", {
      key: "SSMRoleArn",
      description: "Arn of the SSMRole.",
      value: this.ssmAdminRoleArn,
    });

    const lambdaLayer: LayerVersion = this.lambdaLayer();
    this.layerArn = lambdaLayer.layerVersionArn!.toString();
    new CfnOutput(this, "LayerArn", {
      key: "LayerArn",
      description: "ARN for Lambda layer",
      value: this.layerArn,
    });

    const table: Table = this.dynamodDB();
    this.tableName = table.tableName;
    new cdk.CfnOutput(this, "TableArn", {
      key: "TableArn",
      description: "ARN for DynamoDB Table",
      value: table.tableArn,
    });
  }

  s3CentralisedBucket(): Bucket {
    const bucket: Bucket = new Bucket(this, "CentralizedS3Bucket", {
      bucketName: this.s3BucketName,
      blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    const athenaRuleExpiration: number =
      this.DEFAULT_EXPIRATION_FOR_ATHENA_QUERY;
    bucket.addLifecycleRule({
      id: "Expire Athena Query logs",
      enabled: true,
      expiration: Duration.days(athenaRuleExpiration),
      prefix: this.DEFAULT_ATHENA_QUERY_PREFIX,
    });

    const logRuleExpiration: number = this.DEFAULT_EXPIRATION_FOR_LOGS;
    bucket.addLifecycleRule({
      id: "Expire SSM Logs",
      enabled: true,
      expiration: Duration.days(logRuleExpiration),
      prefix: this.DEFAULT_LOGS_PREFIX,
    });

    const reportsRuleTransition: number = this.DEFAULT_TRANSITION_FOR_REPORTS;
    const storageClass: string = this.DEFAULT_REPORTS_TRANSITION_CLASS;
    const reportsTransitionClass: StorageClass = new StorageClass(storageClass);
    bucket.addLifecycleRule({
      id: "Transition Reports",
      enabled: true,
      prefix: this.DEFAULT_REPORTS_PREFIX,
      transitions: [
        {
          storageClass: reportsTransitionClass,
          transitionAfter: Duration.days(reportsRuleTransition),
        },
      ],
    });

    const reportsRuleExpiration: number = this.DEFAULT_EXPIRATION_FOR_REPORTS;
    bucket.addLifecycleRule({
      id: "Expire Reports",
      enabled: true,
      expiration: Duration.days(reportsRuleExpiration),
      prefix: this.DEFAULT_REPORTS_PREFIX,
    });

    return bucket;
  }

  uploadScriptsLibFolder(s3Bucket: IBucket) {
    new BucketDeployment(this, "UploadLibFolder", {
      sources: [Source.asset(path.join(__dirname, "../scripts/lib"))],
      destinationBucket: s3Bucket,
      destinationKeyPrefix: "scripts/lib",
    });
  }

  dynamodDB(): Table {
    return new Table(this, "DynamoDBTable", {
      tableName: this.tableName,
      removalPolicy: RemovalPolicy.DESTROY,
      partitionKey: {
        name: "Account",
        type: AttributeType.STRING,
      },
      sortKey: {
        name: "Region",
        type: AttributeType.STRING,
      },
      pointInTimeRecovery: true,
    });
  }

  s3EventsQueue(): Queue {
    const deadLetterQueue: Queue = new Queue(this, "S3EventsDLQueue", {
      queueName: this.defaultDLQueueName,
      retentionPeriod: Duration.days(this.DEFAULT_MESSAGE_RETENTION_IN_DAYS),
      maxMessageSizeBytes: this.DEFAULT_MAX_MESSAGE_SIZE!,
      encryption: QueueEncryption.SQS_MANAGED,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    this.s3EventsDlQueueArn = deadLetterQueue.queueArn;
    new CfnOutput(this, "S3EventsDLQueueArn", {
      key: "S3EventsDLQueueArn",
      description: "ARN of the S3 events dead letter SQS",
      value: deadLetterQueue.queueArn,
    });

    const s3EventsQueue: Queue = new Queue(this, "S3EventsQueue", {
      queueName: this.defaultQueueName,
      retentionPeriod: Duration.days(this.DEFAULT_MESSAGE_RETENTION_IN_DAYS),
      maxMessageSizeBytes: this.DEFAULT_MAX_MESSAGE_SIZE,
      encryption: QueueEncryption.SQS_MANAGED,
      removalPolicy: RemovalPolicy.DESTROY,
      deadLetterQueue: {
        maxReceiveCount: this.DEFAULT_MAX_RECEIVE_COUNT,
        queue: deadLetterQueue,
      },
    });
    this.s3EventsQueueArn = s3EventsQueue.queueArn;

    s3EventsQueue.addToResourcePolicy(
      new PolicyStatement({
        principals: [new ServicePrincipal("s3.amazonaws.com")],
        actions: ["SQS:SendMessage"],
        resources: [s3EventsQueue.queueArn],
        conditions: {
          ArnEquals: { "aws:SourceArn": `arn:aws:s3:::${this.s3BucketName}` },
          StringEquals: { "aws:SourceAccount": Fn.sub("${AWS::AccountId}") },
        },
      }),
    );
    return s3EventsQueue;
  }

  ssmAdminRole(): Role {
    const servicePrincipal = new ServicePrincipal(
      "ssm.amazonaws.com",
    ).withConditions({
      StringEquals: {
        "aws:SourceAccount": Fn.sub("${AWS::AccountId}"),
      },
      ArnLike: {
        "aws:SourceArn": Fn.sub(
          "arn:${AWS::Partition}:ssm:*:${AWS::AccountId}:automation-execution/*",
        ),
      },
    });

    const role: Role = new Role(this, "SSMAdministrationRole", {
      roleName: this.ssmAdminRoleName,
      assumedBy: servicePrincipal,
      description: "Role used to assume SSM execution roles in target accounts",
    });

    role.addToPolicy(
      new PolicyStatement({
        sid: "AssumeRole",
        actions: ["sts:AssumeRole"],
        resources: [
          Fn.sub(
            "arn:${AWS::Partition}:iam::*:role/*-SSMAutomationExecutionRole*",
          ),
        ],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "ListChildAccounts",
        actions: ["organizations:ListAccountsForParent"],
        resources: ["*"],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "PassRoleToLambdaRole",
        actions: ["iam:PassRole"],
        resources: [
          Fn.sub(
            "arn:aws:iam::${AWS::AccountId}:role/*-LambdaRole-${AWS::Region}",
          ),
        ],
      }),
    );

    return role;
  }

  lambdaLayer(): LayerVersion {
    // Lambda layer creation
    return new LayerVersion(this, "CustomLayer", {
      layerVersionName: this.defaultLayerName,
      compatibleRuntimes: [
        Runtime.PYTHON_3_10,
        Runtime.PYTHON_3_11,
        Runtime.PYTHON_3_12,
      ],
      description:
        "Lambda layer having code to fetch targets and EKS clusters from multiple sources",
      code: Code.fromAsset(path.join(__dirname, "../lambdas/layer/")),
    });
  }
}
