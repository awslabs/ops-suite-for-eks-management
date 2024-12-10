import { SSMRole } from "./config";

export interface OrchestratorConfig {
  readonly enabled?: boolean;
  baseline: Baseline;
  readonly reportGenerator: ReportGenerator;
  readonly summary: Summary;
  readonly backup: Backup;
  readonly upgrade: Upgrade;
  readonly restApi: LambdaRestApi;
  readonly quicksight: Quicksight;
}

export interface S3Bucket {
  name?: string;
  readonly logsPrefix?: string;
  readonly expirationForLogs?: number;
  readonly athenaQueryPrefix?: string;
  readonly expirationForAthenaQuery?: number;
  reportsPrefix?: string;
  readonly reportsTransitionClass?: string;
  readonly transitionForReports?: number;
  readonly expirationForReports?: number;
  readonly endOfLifePrefix?: string;
}

export interface S3EventsQueue {
  name?: string;
  dlName?: string;
  messageRetentionInDays?: number;
  maximumMessageSize?: number;
  maxReceiveCount?: number;
}

export interface LambdaLayer {
  name?: string;
}

export interface ReportGenerator {
  readonly glueCrawlerSchedule: string;
  s3Bucket: string;
  s3EventsQueueArn: string;
  s3EventsDlQueueArn: string;
}

export interface Baseline {
  readonly s3Bucket: S3Bucket;
  readonly s3EventsQueue: S3EventsQueue;
  readonly tenantOnboarding: TenantOnboarding;
  readonly ssmAdminRole: SSMRole;
  readonly lambdaLayer: LambdaLayer;
}

export interface TenantOnboarding {
  readonly dynamoDB: DynamoDB;
}

export interface DynamoDB {
  name?: string;
}

export interface MaintenanceWindow {
  readonly enabled?: boolean;
  name: string;
  roleName: string;
  readonly schedule: string;
  readonly timezone: string;
  readonly cutoff: number;
  readonly duration: number;
  readonly description: string;
}

export interface Solution {
  readonly enabled?: boolean;
  roleName?: string;
  readonly maintenanceWindow: MaintenanceWindow;
  tableName?: string;
  layerArn?: string;
  functionName?: string;
  ssmAdminRole?: string;
  documentName?: string;
  enableSSMCloudWatchLogsInTarget?: string;
  cloudWatchLogGroupName?: string;
}

export interface Summary extends Solution {}

export interface Backup extends Solution {
  storageBucketPrefix: string;
  veleroVersion: string;
}

export interface Upgrade extends Solution {}

export interface LambdaRestApi {
  readonly enabled?: boolean;
  lambdaRoleName: string;
  apiRoleName: string;
  layerArn?: string;
  functionName?: string;
  athenaDataSource?: string;
  glueDatabase?: string;
  summaryFunction?: string;
  backupFunction?: string;
  upgradeFunction?: string;
  restApiName: string;
  allowOrigins: string[];
  allowMethods: string[];
}

export interface Quicksight {
  readonly enabled?: boolean;
  readonly quickSightUserArn: string;
  readonly quickSightIAMRoleArn?: string;
  readonly athenaWorkGroup?: string;
  readonly databaseName?: string;
  readonly summary: FeatureEnablement;
  readonly backup: FeatureEnablement;
  readonly upgrade: FeatureEnablement;
}

export interface FeatureEnablement {
  readonly enabled?: boolean;
}
