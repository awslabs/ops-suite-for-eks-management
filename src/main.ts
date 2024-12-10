import { App, Tags, Aspects } from "aws-cdk-lib";
import input from "../proton-inputs.json";

import { AwsSolutionsChecks, NagSuppressions } from "cdk-nag";
import { TenantBaselineStack } from "./TenantBaselineStack";
import { OrchestratorBaselineStack } from "./OrchestratorBaselineStack";
import { BastionHostStack } from "./BastionHostStack";
import eks_tenant_baseline_suppressions from "./tenant/eks-tenant-baseline-suppressions.json";
import eks_tenant_bastion_host_suppressions from "./tenant/eks-tenant-bastion-host-suppressions.json";
import eks_orchestrator_account_suppressions from "./orchestrator/eks-orchestrator-account-suppressions.json";

// for development, use account/region from cdk cli
const devEnv = {
  account: process.env.CDK_DEPLOY_ACCOUNT,
  region: process.env.CDK_DEPLOY_REGION,
};

const protonInputs: any = input.environment?.inputs || {};

const app: App = new App();

// Tag all AWS resources
Tags.of(app).add("application", "eks-ops");

// Simple rule informational messages
Aspects.of(app).add(new AwsSolutionsChecks());

protonInputs.resourcePrefix = process.env.CDK_QUALIFIER || "eks";
const storageBucketPrefix: string = `${protonInputs.resourcePrefix}-velero-backup`;

if (protonInputs.tenantAccountConfig.enabled) {
  let eks_tenant_baseline = new TenantBaselineStack(
    app,
    "eks-tenant-baseline",
    {
      env: devEnv,
      config: protonInputs.tenantAccountConfig,
      resourcePrefix: protonInputs.resourcePrefix,
      storageBucketPrefix: storageBucketPrefix,
    },
  );

  for (let suppression in eks_tenant_baseline_suppressions) {
    NagSuppressions.addResourceSuppressionsByPath(
      eks_tenant_baseline,
      eks_tenant_baseline_suppressions[suppression].path,
      eks_tenant_baseline_suppressions[suppression].suppression,
    );
  }

  let roleCount: number = 1;
  for (let tenant of protonInputs.tenantAccountConfig.tenants) {
    const bastionHostStack = new BastionHostStack(
      app,
      "eks-tenant-bastion-host",
      {
        env: devEnv,
        config: tenant,
        resourcePrefix: protonInputs.resourcePrefix,
        roleCount,
      },
    );
    for (let suppression in eks_tenant_bastion_host_suppressions) {
      NagSuppressions.addResourceSuppressionsByPath(
        bastionHostStack,
        eks_tenant_bastion_host_suppressions[suppression].path,
        eks_tenant_bastion_host_suppressions[suppression].suppression,
      );
    }
  }
}

if (protonInputs.orchestratorAccountConfig.enabled) {
  const orchestratorBaselineStack = new OrchestratorBaselineStack(
    app,
    "eks-orchestrator-account",
    {
      env: devEnv,
      config: protonInputs.orchestratorAccountConfig,
      resourcePrefix: protonInputs.resourcePrefix,
      storageBucketPrefix: storageBucketPrefix,
    },
  );
  for (let suppression in eks_orchestrator_account_suppressions) {
    NagSuppressions.addResourceSuppressionsByPath(
      orchestratorBaselineStack,
      eks_orchestrator_account_suppressions[suppression].path,
      eks_orchestrator_account_suppressions[suppression].suppression,
    );
  }
}

app.synth();
