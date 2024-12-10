import { Tenant } from "./config/TenantConfig";
import { Stack, StackProps } from "aws-cdk-lib";
import { Construct } from "constructs";
import { BastionHostConstruct } from "./tenant/iac/BastionHost";

export interface TenantVPCStackProps extends StackProps {
  readonly config: Tenant;
  readonly resourcePrefix: string;
  readonly roleCount: number;
}

export class BastionHostStack extends Stack {
  constructor(scope: Construct, id: string, props: TenantVPCStackProps) {
    super(scope, id, props);
    const accountId: string = this.account;

    new BastionHostConstruct(
      this,
      "BastionHostConstruct",
      {
        config: props.config,
        accountId,
      },
      props.resourcePrefix,
      props.roleCount,
    );
  }
}
