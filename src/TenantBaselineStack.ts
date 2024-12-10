import { TenantConfig } from "./config/TenantConfig";
import { Stack, StackProps } from "aws-cdk-lib";
import { Construct } from "constructs";
import { BaselineConstruct } from "./tenant/iac/Baseline";

export interface TenantBaselineStackProps extends StackProps {
  readonly config: TenantConfig;
  readonly resourcePrefix: string;
  readonly storageBucketPrefix: string;
}

export class TenantBaselineStack extends Stack {
  constructor(scope: Construct, id: string, props: TenantBaselineStackProps) {
    super(scope, id, props);
    new BaselineConstruct(
      this,
      "Baseline",
      props.resourcePrefix,
      props.storageBucketPrefix,
      {
        config: props.config,
      },
    );
  }
}
