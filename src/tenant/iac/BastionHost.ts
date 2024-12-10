import { BastionHostRole, Tenant } from "../../config/TenantConfig";
import { Construct } from "constructs";
import {
  InstanceProfile,
  IRole,
  ManagedPolicy,
  PolicyStatement,
  Role,
  ServicePrincipal,
} from "aws-cdk-lib/aws-iam";
import * as cdk from "aws-cdk-lib";
import { Fn, Tags } from "aws-cdk-lib";
import {
  Instance,
  InstanceClass,
  InstanceSize,
  InstanceType,
  MachineImage,
  SubnetFilter,
  SubnetSelection,
  Vpc,
} from "aws-cdk-lib/aws-ec2";

export interface BaselineConstructProps {
  readonly config: Tenant;
  readonly accountId: string;
}

export class BastionHostConstruct extends Construct {
  /**
   * S3 Bucket name
   */
  public roleArn: string;
  public instanceProfileArn: string;
  public instanceId: string;

  constructor(
    scope: Construct,
    id: string,
    props: BaselineConstructProps,
    resourcePrefix: string,
    roleCount: number,
  ) {
    super(scope, id);
    this.resources(props, resourcePrefix, roleCount);
  }

  resources(
    props: BaselineConstructProps,
    resourcePrefix: string,
    roleCount: number,
  ) {
    let bastionHostRole: IRole;
    if (props.config.bastionHostRole.enabled) {
      bastionHostRole = this.bastionHostRole(
        props.config.bastionHostRole,
        resourcePrefix,
        props.accountId,
        roleCount,
      );
      this.bastionHostInstanceProfile(
        props.config.bastionHostRole,
        bastionHostRole,
        resourcePrefix,
        roleCount,
      );
    } else {
      const roleSuffix: string = `bastion-host-role - ${roleCount}`;
      const defaultName: string = `${resourcePrefix}-${roleSuffix}`;
      bastionHostRole = Role.fromRoleName(this, "Role", defaultName, {
        mutable: false,
      });
    }

    if (bastionHostRole.roleName in [null, undefined]) {
      console.error(
        `${this.bastionHostRole} not present. Please enable it to create it.`,
      );
      return;
    }

    if (props.config.bastionHost.enabled) {
      this.bastionHost(props.config, bastionHostRole);
    }
  }

  bastionHost(config: Tenant, bastionHostRole: IRole): Instance {
    const vpc = Vpc.fromLookup(this, "vpc", {
      vpcId: config.bastionHost.vpcId,
    });
    const selection: SubnetSelection = vpc.selectSubnets({
      subnetFilters: [SubnetFilter.byIds([config.bastionHost.subnetId])],
    });
    let instance = new Instance(this, "BastionHost", {
      vpc,
      machineImage: MachineImage.latestAmazonLinux2023(),
      instanceType: InstanceType.of(InstanceClass.T2, InstanceSize.MICRO),
      role: bastionHostRole,
    });
    this.instanceId = instance.instanceId;

    Tags.of(instance).add("EKSManagementNode", "EKSManagementBastionHost");

    new cdk.CfnOutput(this, "CfnOutputInstanceId", {
      key: "InstanceId",
      description: "Bastion Host InstanceId.",
      value: instance.instanceId,
    });
    return instance;
  }

  bastionHostRole(
    config: BastionHostRole,
    resourcePrefix: string,
    accountId: string,
    roleCount: number,
  ): Role {
    let region = Fn.sub("${AWS::Region}");
    const roleSuffix: string = `bastion-host-role-${roleCount}-${region}`;
    const defaultName: string = `${resourcePrefix}-${roleSuffix}`;

    const role: Role = new Role(this, "BastionHostRole", {
      roleName: config.name || defaultName,
      assumedBy: new ServicePrincipal("ec2.amazonaws.com"),
      description: "Bastion host role in tenant accounts",
    });

    role.addManagedPolicy(
      ManagedPolicy.fromManagedPolicyArn(
        this,
        "AmazonSSMManagedInstanceCore",
        "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
      ),
    );

    role.addManagedPolicy(
      ManagedPolicy.fromManagedPolicyArn(
        this,
        "CloudWatchAgentServerPolicy",
        "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy",
      ),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "ListClusters",
        actions: ["eks:ListClusters"],
        resources: ["*"],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "ClusterPermission",
        actions: [
          "eks:DescribeCluster",
          "eks:ListInsights",
          "eks:DescribeInsight",
          "eks:ListAddons",
          "eks:ListFargateProfiles",
          "eks:DescribeFargateProfile",
          "eks:DescribeUpdate",
          "eks:DescribeNodegroup",
          "eks:DescribeAddon",
          "eks:DescribeInsight",
          "eks:ListInsights",
          "eks:DescribeAddonVersions",
          "eks:ListNodegroups",
          "eks:TagResource",
        ],
        resources: [
          cdk.Fn.sub("arn:aws:eks:${AWS::Region}:${AWS::AccountId}:cluster/*"),
          cdk.Fn.sub(
            "arn:aws:eks:${AWS::Region}:${AWS::AccountId}:nodegroup/*/*/*",
          ),
          cdk.Fn.sub(
            "arn:aws:eks:${AWS::Region}:${AWS::AccountId}:addon/*/*/*",
          ),
          cdk.Fn.sub(
            "arn:aws:eks:${AWS::Region}:${AWS::AccountId}:fargateprofile/*/*/*",
          ),
          cdk.Fn.sub(
            "arn:aws:eks:${AWS::Region}:${AWS::AccountId}:identityproviderconfig/*/*/*/*",
          ),
        ],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "GetRole",
        actions: [
          "iam:GetRole",
          "iam:PassRole",
          "iam:PutRolePolicy",
          "iam:CreateRole",
        ],
        resources: [`arn:aws:iam::${accountId}:role/${resourcePrefix}-*`],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "ListBucket",
        actions: ["s3:ListBucket"],
        resources: [`arn:aws:s3:::${resourcePrefix}-*`],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "S3Object",
        actions: ["s3:GetObject", "s3:PutObject", "s3:PutObjectAcl"],
        resources: [`arn:aws:s3:::${resourcePrefix}-*`],
      }),
    );
    if (config.backup.enabled) {
      role.addToPolicy(
        new PolicyStatement({
          sid: "DescribeAddonVersions",
          actions: ["eks:DescribeAddonVersions"],
          resources: [`*`],
        }),
      );
      role.addToPolicy(
        new PolicyStatement({
          sid: "ListOpenIDConnectProviders",
          actions: ["iam:ListOpenIDConnectProviders"],
          resources: [
            cdk.Fn.sub("arn:aws:iam::${AWS::AccountId}:oidc-provider/*"),
          ],
        }),
      );
      role.addToPolicy(
        new PolicyStatement({
          sid: "OpenId",
          actions: [
            "iam:GetOpenIDConnectProvider",
            "iam:CreateOpenIDConnectProvider",
            "iam:TagOpenIDConnectProvider",
          ],
          resources: ["*"],
        }),
      );
    }
    if (config.upgrade.enabled) {
      role.addToPolicy(
        new PolicyStatement({
          sid: "OpenId",
          actions: [
            "iam:GetOpenIDConnectProvider",
            "iam:CreateOpenIDConnectProvider",
            "iam:TagOpenIDConnectProvider",
          ],
          resources: ["*"],
        }),
      );

      role.addToPolicy(
        new PolicyStatement({
          sid: "UpdateAddon",
          actions: [
            "eks:UpdateAddon",
            "eks:UpdateClusterVersion",
            "eks:UpdateNodegroupVersion",
          ],
          resources: [
            cdk.Fn.sub(
              "arn:aws:eks:${AWS::Region}:${AWS::AccountId}:cluster/*",
            ),
            cdk.Fn.sub(
              "arn:aws:eks:${AWS::Region}:${AWS::AccountId}:nodegroup/*/*/*",
            ),
            cdk.Fn.sub(
              "arn:aws:eks:${AWS::Region}:${AWS::AccountId}:addon/*/*/*",
            ),
            cdk.Fn.sub(
              "arn:aws:eks:${AWS::Region}:${AWS::AccountId}:fargateprofile/*/*/*",
            ),
            cdk.Fn.sub(
              "arn:aws:eks:${AWS::Region}:${AWS::AccountId}:identityproviderconfig/*/*/*/*",
            ),
          ],
        }),
      );

      role.addToPolicy(
        new PolicyStatement({
          sid: "ListStacks",
          actions: ["cloudformation:ListStacks"],
          resources: ["*"],
        }),
      );
      role.addToPolicy(
        new PolicyStatement({
          sid: "StackOperations",
          actions: [
            "cloudformation:CreateStack",
            "cloudformation:DescribeStacks",
            "cloudformation:GetTemplate",
          ],
          resources: [
            cdk.Fn.sub(
              "arn:aws:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/eksctl-*/*",
            ),
          ],
        }),
      );
      role.addToPolicy(
        new PolicyStatement({
          sid: "VPCOperations",
          actions: [
            "ec2:DescribeSubnets",
            "ec2:DescribeVpcs",
            "ec2:DescribeLaunchTemplateVersions",
          ],
          resources: ["*"],
        }),
      );
    }
    this.roleArn = role.roleArn;
    return role;
  }

  bastionHostInstanceProfile(
    config: BastionHostRole,
    role: IRole,
    resourcePrefix: string,
    roleCount: number,
  ): InstanceProfile {
    let region = Fn.sub("${AWS::Region}");
    const roleSuffix: string = `bastion-host-profile-${roleCount}-${region}`;
    const defaultName: string = `${resourcePrefix}-${roleSuffix}`;

    const instanceProfile = new InstanceProfile(this, "EC2BastionHostProfile", {
      instanceProfileName: config.name || defaultName,
      path: "/",
      role,
    });

    this.instanceProfileArn = instanceProfile.instanceProfileArn;
    new cdk.CfnOutput(this, "CfnOutputInstanceProfile", {
      key: "InstanceProfileArn",
      description: "ARN of the InstanceProfile.",
      value: instanceProfile.instanceProfileArn,
    });

    new cdk.CfnOutput(this, "CfnOutputRoleARN", {
      key: "RoleArn",
      description: "ARN of the Bastion Host Role.",
      value: this.roleArn.toString(),
    });

    return instanceProfile;
  }
}
