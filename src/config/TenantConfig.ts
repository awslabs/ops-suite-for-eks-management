import { SSMRole } from "./config";
import { Backup, Upgrade } from "./OrchestratorConfig";

export interface TenantConfig {
  readonly enabled?: boolean;
  readonly orchestratorAccountId: string;
  readonly tenants: Tenant[];
  s3BucketPrefix: string;
}

export interface Baseline {
  readonly enabled?: boolean;
  readonly s3Bucket: S3Bucket;
  readonly ssmExecutionRole: SSMRole;
}

export interface S3Bucket {
  readonly enabled?: boolean;
  readonly name?: string;
  readonly s3BucketPrefix?: string;
  readonly logsPrefix?: string;
  readonly expirationForLogs?: number;
  readonly athenaQueryPrefix?: string;
  readonly expirationForAthenaQuery?: number;
  readonly reportsPrefix?: string;
  readonly reportsTransitionClass?: string;
  readonly transitionForReports?: number;
  readonly expirationForReports?: number;
  readonly endOfLifePrefix?: string;
}

export interface Tenant {
  readonly enabled?: boolean;
  readonly bastionHost: BastionHost;
  readonly bastionHostRole: BastionHostRole;
}

export interface BastionHost {
  readonly enabled?: boolean;
  readonly vpcId: string;
  readonly subnetId: string;
  readonly instanceType: string;
}

export interface BastionHostRole {
  readonly enabled?: boolean;
  readonly name?: string;
  readonly clusterArns: string[];
  readonly upgrade: Upgrade;
  readonly backup: Backup;
}
