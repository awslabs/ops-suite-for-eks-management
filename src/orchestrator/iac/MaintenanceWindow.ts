import { MaintenanceWindow } from "../../config/OrchestratorConfig";
import { Construct } from "constructs";
import { PolicyStatement, Role, ServicePrincipal } from "aws-cdk-lib/aws-iam";
import {
  CfnMaintenanceWindow,
  CfnMaintenanceWindowTask,
} from "aws-cdk-lib/aws-ssm";
import { Function } from "aws-cdk-lib/aws-lambda";
import { Fn } from "aws-cdk-lib";

export interface MaintenanceWindowProps {
  readonly config: MaintenanceWindow;
  readonly lambdaFunction: Function;
  roleName?: string;
}

export class MaintenanceWindowConstruct extends Construct {
  DEFAULT_WINDOW_CUTOFF: number = 1;
  DEFAULT_WINDOW_DURATION: number = 2;

  constructor(
    scope: Construct,
    id: string,
    resourcePrefix: string,
    props: MaintenanceWindowProps,
  ) {
    super(scope, id);

    const region = Fn.sub("${AWS::Region}");
    const defaultedProps: MaintenanceWindowProps = this.defaults(
      resourcePrefix,
      props,
      region,
    );
    this.resources(defaultedProps);
  }

  defaults(
    resourcePrefix: string,
    props: MaintenanceWindowProps,
    region: string,
  ): MaintenanceWindowProps {
    const properties: MaintenanceWindowProps = props;

    // Defaulting the task role
    const defaultRoleName: string = `${resourcePrefix}-maintenance-task-role-${region}`;
    properties.roleName = props.config.roleName || defaultRoleName;

    // Defaulting maintenance window name
    const defaultWindowName: string = `${resourcePrefix}-maintenance-window`;
    properties.config.name = props.config.name || defaultWindowName;
    return properties;
  }

  resources(props: MaintenanceWindowProps) {
    if (props.config.enabled) {
      const taskRole: Role = this.taskRole(props);
      const maintenanceWindow: CfnMaintenanceWindow =
        this.maintenanceWindow(props);
      this.maintenanceWindowTask(maintenanceWindow, taskRole, props);
    }
  }

  taskRole(props: MaintenanceWindowProps): Role {
    const maintenanceTaskAssumeRole: Role = new Role(
      this,
      "MaintenanceTaskAssumeRole",
      {
        assumedBy: new ServicePrincipal("ssm.amazonaws.com"),
        roleName: props.roleName,
        description: "Allows Maintenance Window to invoke Lambda function",
      },
    );

    maintenanceTaskAssumeRole.addToPolicy(
      new PolicyStatement({
        actions: ["lambda:InvokeFunction"],
        resources: [props.lambdaFunction.functionArn],
      }),
    );

    return maintenanceTaskAssumeRole;
  }

  maintenanceWindow(props: MaintenanceWindowProps): CfnMaintenanceWindow {
    return new CfnMaintenanceWindow(this, "MaintenanceWindow", {
      allowUnassociatedTargets: false,
      cutoff: props.config.cutoff || this.DEFAULT_WINDOW_CUTOFF,
      description: props.config.description,
      duration: props.config.duration || this.DEFAULT_WINDOW_DURATION,
      name: props.config.name,
      schedule: props.config.schedule,
      scheduleTimezone: props.config.timezone,
    });
  }

  maintenanceWindowTask(
    maintenanceWindow: CfnMaintenanceWindow,
    taskRole: Role,
    props: MaintenanceWindowProps,
  ): CfnMaintenanceWindowTask {
    return new CfnMaintenanceWindowTask(this, "LambdaMaintenanceTask", {
      description: "Invoke EKSManagement-UpgradeAutomation-Function",
      name: props.config.name + "MaintenanceLambdaTask",
      windowId: maintenanceWindow.ref,
      taskType: "LAMBDA",
      taskArn: props.lambdaFunction.functionArn,
      serviceRoleArn: taskRole.roleArn,
      priority: 1,
    });
  }
}
