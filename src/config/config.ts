// Common
export interface BaseConfig {
  resourcePrefix: string;
}

export interface SSMRole {
  readonly enabled?: boolean;
  name?: string;
  readonly orchestratorAccountId: string;
}

export interface maintenanceWindow {
  readonly enabled?: boolean;
  readonly name: string;
  readonly schedule: string;
  readonly timezone: string;
  readonly cutoff: number;
  readonly duration: number;
  readonly description: string;
}
