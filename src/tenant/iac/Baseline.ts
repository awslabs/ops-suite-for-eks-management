import { TenantConfig } from "../../config/TenantConfig";
import { Construct } from "constructs";
import { BlockPublicAccess, Bucket } from "aws-cdk-lib/aws-s3";
import { CfnOutput, Fn, RemovalPolicy } from "aws-cdk-lib";
import {
  AccountRootPrincipal,
  ArnPrincipal,
  Effect,
  ManagedPolicy,
  PolicyStatement,
  Role,
  ServicePrincipal,
} from "aws-cdk-lib/aws-iam";

export interface BaselineConstructProps {
  readonly config: TenantConfig;
}

export class BaselineConstruct extends Construct {
  /**
   * S3 Bucket name
   */
  public s3BucketName: string;
  public s3BucketArn: string;
  public ssmExecutionRoleArn: string;
  public ssmExecutionRoleName: string;

  constructor(
    scope: Construct,
    id: string,
    resourcePrefix: string,
    storageBucketPrefix: string,
    props: BaselineConstructProps,
  ) {
    super(scope, id);
    this.resources(props, resourcePrefix, storageBucketPrefix);
  }

  resources(
    props: BaselineConstructProps,
    resourcePrefix: string,
    storageBucketPrefix: string,
  ) {
    const accountId: string = Fn.sub("${AWS::AccountId}");
    const region: string = Fn.sub("${AWS::Region}");

    storageBucketPrefix =
      storageBucketPrefix || "eksmanagement-automation-velero-backup";
    this.s3BucketName = `${storageBucketPrefix}-${accountId}-${region}`;

    const roleSuffix: string = "SSMAutomationExecutionRole";
    this.ssmExecutionRoleName = `${resourcePrefix}-${roleSuffix}-${region}`;

    const s3Bucket: Bucket = this.s3BackupBucket(this.s3BucketName);
    this.s3BucketArn = s3Bucket.bucketArn;

    const orchestratorId = props.config.orchestratorAccountId;
    const role: Role = this.ssmExecutionRole(orchestratorId);
    this.ssmExecutionRoleArn = role.roleArn;
    new CfnOutput(this, "SSMExecutionRoleArn", {
      key: "SSMExecutionRoleArn",
      description: "Arn of the SSMRole.",
      value: this.ssmExecutionRoleArn,
    });
  }

  s3BackupBucket(s3BucketName: string): Bucket {
    return new Bucket(this, "BackupS3Bucket", {
      bucketName: s3BucketName,
      blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });
  }

  ssmExecutionRole(orchestratorId: string): Role {
    const roleName: string = this.ssmExecutionRoleName;

    const role: Role = new Role(this, "SSMExecutionRole", {
      roleName: roleName,
      assumedBy: new ArnPrincipal(`arn:aws:iam::${orchestratorId}:root`),
      description: "Role used to run SSM execution roles in tenant account",
    });

    role.assumeRolePolicy?.addStatements(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ["sts:AssumeRole"],
        principals: [
          new ServicePrincipal("ssm.amazonaws.com", {
            conditions: {
              StringEquals: {
                "aws:SourceAccount": Fn.sub("${AWS::AccountId}"),
              },
              ArnLike: {
                "aws:SourceArn": Fn.sub(
                  "arn:${AWS::Partition}:ssm:*:${AWS::AccountId}:automation-execution/*",
                ),
              },
            },
          }),
        ],
      }),
    );

    role.assumeRolePolicy?.addStatements(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ["sts:AssumeRole"],
        principals: [new AccountRootPrincipal()],
      }),
    );

    role.addManagedPolicy(
      ManagedPolicy.fromManagedPolicyArn(
        this,
        "SSMExecutionManagedPolicy",
        "arn:aws:iam::aws:policy/service-role/AmazonSSMAutomationRole",
      ),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "ListResources",
        actions: [
          "resource-groups:ListGroupResources",
          "tag:GetResources",
          "ec2:DescribeInstances",
        ],
        resources: ["*"],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "PassRole",
        actions: ["iam:PassRole"],
        resources: [
          Fn.sub(
            "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/${roleName}",
            {
              roleName,
            },
          ),
        ],
      }),
    );
    return role;
  }
}
