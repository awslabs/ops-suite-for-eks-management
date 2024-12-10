import { ReportGenerator } from "../../config/OrchestratorConfig";
import { Construct } from "constructs";
import { CfnDataCatalog, CfnWorkGroup } from "aws-cdk-lib/aws-athena";
import { CfnCrawler, CfnDatabase } from "aws-cdk-lib/aws-glue";
import {
  ManagedPolicy,
  PolicyStatement,
  Role,
  ServicePrincipal,
} from "aws-cdk-lib/aws-iam";
import { Fn, RemovalPolicy } from "aws-cdk-lib";
import { getAthenaWorkGroupName, getGlueDatabaseName } from "./Utils";

export interface ReportGeneratorConstructProps {
  readonly config: ReportGenerator;
}

export class ReportGeneratorConstruct extends Construct {
  public roleArn: string;
  public glueDatabaseRef: string;
  public dataCatalogName: string;
  public athenaWorkGroupName: string;
  public glueS3CrawlerName: string;

  constructor(
    scope: Construct,
    id: string,
    props: ReportGeneratorConstructProps,
    resourcePrefix: string,
  ) {
    super(scope, id);
    const accountId: string = Fn.sub("${AWS::AccountId}");
    this.resources(props, resourcePrefix, accountId);
  }

  resources(
    props: ReportGeneratorConstructProps,
    resourcePrefix: string,
    accountId: string,
  ) {
    this.athenaDataCatalog(props, resourcePrefix, accountId);
    this.glueCrawlerRole(props, resourcePrefix);
    this.glueDatabase(props, resourcePrefix, accountId);
    this.glueCrawler(props, resourcePrefix);
    this.athenaWorkgroup(props, resourcePrefix);
  }

  athenaDataCatalog(
    props: ReportGeneratorConstructProps,
    resourcePrefix: string,
    accountId: string,
  ) {
    const roleSuffix: string = "datacatalog";
    const defaultName: string = `${resourcePrefix}-${roleSuffix}`;

    const cfnDataCatalog = new CfnDataCatalog(this, "AthenaDataCatalog", {
      name: defaultName,
      type: "GLUE",
      description: "Data catalog for the EKS Management Automation",
      parameters: {
        "catalog-id": accountId,
      },
    });
    cfnDataCatalog.applyRemovalPolicy(RemovalPolicy.DESTROY);
    this.dataCatalogName = cfnDataCatalog.name;
  }

  glueCrawlerRole(
    props: ReportGeneratorConstructProps,
    resourcePrefix: string,
  ): Role {
    let region = Fn.sub("${AWS::Region}");

    const s3EventsQueueArn: string = props.config.s3EventsQueueArn;
    const s3EventsDlQueueArn: string = props.config.s3EventsDlQueueArn;
    const roleSuffix: string = "glue-crawler-role";
    const defaultName: string = `${resourcePrefix}-${roleSuffix}-${region}`;

    const role: Role = new Role(this, "GlueCrawlerRole", {
      roleName: defaultName,
      assumedBy: new ServicePrincipal("glue.amazonaws.com"),
      description: "GlueCrawlerRole in orchestrator account",
    });

    role.addManagedPolicy(
      ManagedPolicy.fromManagedPolicyArn(
        this,
        "AWSGlueServiceRole",
        "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole",
      ),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "ReadS3Bucket",
        actions: ["s3:PutObject", "s3:GetObject"],
        resources: [`arn:aws:s3:::${props.config.s3Bucket!}/reports/*`],
      }),
    );

    if (s3EventsQueueArn != null && s3EventsDlQueueArn != null) {
      role.addToPolicy(
        new PolicyStatement({
          sid: "SQSPermissions",
          actions: [
            "sqs:DeleteMessage",
            "sqs:GetQueueUrl",
            "sqs:ListDeadLetterSourceQueues",
            "sqs:PurgeQueue",
            "sqs:ReceiveMessage",
            "sqs:GetQueueAttributes",
            "sqs:ListQueueTags",
            "sqs:SetQueueAttributes",
          ],
          resources: [s3EventsQueueArn, s3EventsDlQueueArn],
        }),
      );
    }

    this.roleArn = role.roleArn;
    return role;
  }

  athenaWorkgroup(
    props: ReportGeneratorConstructProps,
    resourcePrefix: string,
  ) {
    const defaultName: string = getAthenaWorkGroupName(resourcePrefix);

    const s3BucketName: string = props.config.s3Bucket!;

    const athenaWorkGroup = new CfnWorkGroup(this, "AthenaWorkGroup", {
      name: defaultName,
      description: "Workgroup for EKS Management tables",
      state: "ENABLED",
      recursiveDeleteOption: true,
      workGroupConfiguration: {
        requesterPaysEnabled: true,
        enforceWorkGroupConfiguration: true,
        resultConfiguration: {
          outputLocation: `s3://${s3BucketName}/athena/query-result`,
        },
      },
    });
    this.athenaWorkGroupName = athenaWorkGroup.name;
  }

  glueDatabase(
    props: ReportGeneratorConstructProps,
    resourcePrefix: string,
    accountId: string,
  ) {
    const defaultName: string = getGlueDatabaseName(resourcePrefix);

    const glueDatabase = new CfnDatabase(this, "GlueDatabase", {
      catalogId: accountId,
      databaseInput: {
        name: defaultName,
        description: "Database for EKS Management Activities",
      },
    });
    this.glueDatabaseRef = glueDatabase.ref;
  }

  glueCrawler(props: ReportGeneratorConstructProps, resourcePrefix: string) {
    const s3BucketName: string = props.config.s3Bucket;
    const s3EventsQueueArn: string = props.config.s3EventsQueueArn;
    const s3EventsDlQueueArn: string = props.config.s3EventsDlQueueArn;

    const roleSuffix: string = "glue-crawler";
    const defaultName: string = `${resourcePrefix}-${roleSuffix}`;

    const glueS3Crawler = new CfnCrawler(this, "GlueS3Crawler", {
      name: defaultName,
      role: this.roleArn,
      databaseName: this.glueDatabaseRef,
      targets: {
        s3Targets: [
          {
            path: `s3://${s3BucketName!}/reports/`,
            eventQueueArn: s3EventsQueueArn,
            dlqEventQueueArn: s3EventsDlQueueArn,
          },
        ],
      },
      recrawlPolicy: {
        recrawlBehavior: "CRAWL_EVENT_MODE",
      },
      schemaChangePolicy: {
        updateBehavior: "UPDATE_IN_DATABASE",
        deleteBehavior: "DEPRECATE_IN_DATABASE",
      },
      schedule: {
        scheduleExpression: `${props.config.glueCrawlerSchedule!}`,
      },
    });
    this.glueS3CrawlerName = glueS3Crawler.name!;
  }
}
