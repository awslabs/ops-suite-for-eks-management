import { Construct } from "constructs";
import {
  Code,
  Function,
  ILayerVersion,
  LayerVersion,
  Runtime,
} from "aws-cdk-lib/aws-lambda";
import { CfnOutput, Duration, Fn } from "aws-cdk-lib";
import {
  AccessLogFormat,
  Cors,
  Deployment,
  JsonSchemaType,
  JsonSchemaVersion,
  LambdaIntegration,
  LogGroupLogDestination,
  MethodResponse,
  Model,
  Resource,
  RestApi,
  Stage,
} from "aws-cdk-lib/aws-apigateway";
import { LambdaRestApi } from "../../config/OrchestratorConfig";
import { HttpMethod } from "aws-cdk-lib/aws-apigatewayv2";
import { LogGroup } from "aws-cdk-lib/aws-logs";
import {
  ManagedPolicy,
  PolicyStatement,
  Role,
  ServicePrincipal,
} from "aws-cdk-lib/aws-iam";
import path from "path";
import { IBucket } from "aws-cdk-lib/aws-s3";

export interface RestApiConstructProps {
  readonly config: LambdaRestApi;
  readonly s3Bucket: IBucket;
  readonly dynamodbTable: string;
  readonly summaryEnabled: boolean;
  readonly backupEnabled: boolean;
  readonly upgradeEnabled: boolean;
}

export class RestApiConstruct extends Construct {
  public function: Function;
  public role: Role;

  private DEFAULT_ATHENA_QUERY_CACHING_MIN: string = "60";
  private DEFAULT_LAMBDA_INVOCATION_TYPE: string = "RequestResponse";
  private DEFAULT_LOG_TYPE: string = "None";

  constructor(
    scope: Construct,
    id: string,
    resourcePrefix: string,
    props: RestApiConstructProps,
  ) {
    super(scope, id);

    const accountId: string = Fn.sub("${AWS::AccountId}");
    const region: string = Fn.sub("${AWS::Region}");

    const defaultedProps: RestApiConstructProps = this.defaults(
      resourcePrefix,
      region,
      props,
    );
    this.resources(resourcePrefix, accountId, region, defaultedProps);
  }

  defaults(
    resourcePrefix: string,
    region: string,
    props: RestApiConstructProps,
  ): RestApiConstructProps {
    const properties: RestApiConstructProps = props;

    // Defaulting rest api name
    const defaultApiName: string = `${resourcePrefix}-lambda-rest-api`;
    properties.config.restApiName = props.config.restApiName || defaultApiName;

    // Defaulting origins and methods to allow
    const defaultOrigin: string[] = Cors.ALL_ORIGINS;
    properties.config.allowOrigins = props.config.allowOrigins || defaultOrigin;

    const defaultMethods: string[] = Cors.ALL_METHODS;
    properties.config.allowMethods =
      props.config.allowMethods || defaultMethods;

    // Defaulting lambda role name
    const defaultLambdaRoleName: string = `${resourcePrefix}-api-lambda-role-${region}`;
    properties.config.lambdaRoleName =
      props.config.lambdaRoleName || defaultLambdaRoleName;

    // Defaulting api role name
    const defaultApiRoleName: string = `${resourcePrefix}-api-role-${region}`;
    properties.config.apiRoleName =
      props.config.apiRoleName || defaultApiRoleName;

    // Defaulting lambda name
    const defaultName: string = `${resourcePrefix}-rest-api-function`;
    properties.config.functionName = props.config.functionName || defaultName;

    return properties;
  }

  resources(
    resourcePrefix: string,
    accountId: string,
    region: string,
    props: RestApiConstructProps,
  ) {
    this.role = this.lambdaRole(resourcePrefix, accountId, region, props);
    this.function = this.lambdaFunction(props);

    const restApi: RestApi = this.createRestApi(props);
    new CfnOutput(this, "Rest Api Id", {
      value: restApi.restApiId,
    });
  }

  lambdaRole(
    resourcePrefix: string,
    accountId: string,
    region: string,
    props: RestApiConstructProps,
  ): Role {
    const restApiConfig: LambdaRestApi = props.config;

    const role: Role = new Role(this, "ApiLambdaRole", {
      assumedBy: new ServicePrincipal("lambda.amazonaws.com"),
      roleName: restApiConfig.lambdaRoleName,
      description:
        "Allows Lambda to access DynamoDB table and Start SSM Automation",
    });

    role.addToPolicy(
      new PolicyStatement({
        sid: "CloudWatchLogs",
        actions: [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ],
        resources: [
          `arn:aws:logs:${region}:${accountId}:log-group:/aws/lambda/${restApiConfig.functionName}:log-stream:*`,
          `arn:aws:logs:${region}:${accountId}:log-group:/aws/lambda/${restApiConfig.functionName}`,
        ],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "LambdaInvocation",
        actions: ["lambda:InvokeFunction"],
        resources: [
          `arn:aws:lambda:${region}:${accountId}:function:${resourcePrefix}-*`,
        ],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "AthenaQueryExecution",
        actions: [
          "athena:StartQueryExecution",
          "athena:StopQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetDataCatalog",
          "athena:GetQueryResults",
          "athena:GetWorkGroup",
        ],
        resources: [
          `arn:aws:athena:${region}:${accountId}:workgroup/*`,
          `arn:aws:athena:${region}:${accountId}:datacatalog/${restApiConfig.athenaDataSource}`,
        ],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "GlueDatabase",
        actions: [
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartitions",
        ],
        resources: [
          `arn:aws:glue:${region}:${accountId}:catalog`,
          `arn:aws:glue:${region}:${accountId}:database/${restApiConfig.glueDatabase}`,
          `arn:aws:glue:${region}:${accountId}:table/${restApiConfig.glueDatabase}/*`,
        ],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "S3AthenaQueryResults",
        actions: [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucketMultipartUploads",
          "s3:AbortMultipartUpload",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:ListMultipartUploadParts",
          "s3:GetBucketPolicy",
          "s3:DeleteBucketPolicy",
          "s3:PutBucketPolicy",
        ],
        resources: [
          `arn:aws:s3:::${props.s3Bucket.bucketName}/*`,
          `arn:aws:s3:::${props.s3Bucket.bucketName}`,
        ],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "AutomationExecution",
        actions: ["ssm:GetAutomationExecution"],
        resources: [
          `arn:aws:ssm:${region}:${accountId}:automation-execution/*`,
        ],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        actions: [
          "dynamodb:BatchGetItem",
          "dynamodb:ConditionCheckItem",
          "dynamodb:GetItem",
          "dynamodb:Scan",
          "dynamodb:Query",
          "dynamodb:BatchWriteItem",
          "dynamodb:PutItem",
          "dynamodb:PartiQLUpdate",
          "dynamodb:PartiQLInsert",
          "dynamodb:UpdateItem",
        ],
        resources: [
          `arn:aws:dynamodb:*:${accountId}:table/${props.dynamodbTable}`,
          `arn:aws:dynamodb:*:${accountId}:table/${props.dynamodbTable}/index/*`,
        ],
      }),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "AssumeRole",
        actions: ["sts:AssumeRole"],
        resources: [
          Fn.sub(
            "arn:${AWS::Partition}:iam::*:role/*-SSMAutomationExecutionRole*",
          ),
        ],
      }),
    );

    return role;
  }

  lambdaFunction(props: RestApiConstructProps): Function {
    const config: LambdaRestApi = props.config;

    const powerToolsLayerARN: string = Fn.sub(
      "arn:aws:lambda:${AWS::Region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:68",
    );
    const powerToolsLayer: ILayerVersion = LayerVersion.fromLayerVersionArn(
      this,
      "AWSLambdaPowertoolsPythonV2",
      powerToolsLayerARN,
    );

    const customLayerArn: string = config.layerArn!;
    const customLayer: ILayerVersion = LayerVersion.fromLayerVersionArn(
      this,
      "CustomLayer",
      customLayerArn,
    );

    return new Function(this, "SummaryHandler", {
      description: "Lambda function integrated with REST API Gateway",
      functionName: config.functionName,
      runtime: Runtime.PYTHON_3_12,
      code: Code.fromAsset(path.join(__dirname, "../lambdas/api")),
      handler: "lambda_function.lambda_handler",
      memorySize: 512,
      timeout: Duration.seconds(600),
      layers: [powerToolsLayer, customLayer],
      role: this.role,
      environment: {
        S3_BUCKET: props.s3Bucket.bucketName || "",
        ATHENA_DATABASE: config.glueDatabase || "",
        ATHENA_DATASOURCE: config.athenaDataSource || "",
        ATHENA_QUERY_CACHING_MIN: this.DEFAULT_ATHENA_QUERY_CACHING_MIN,
        SUMMARY_AUTOMATION_LAMBDA: config.summaryFunction || "",
        BACKUP_AUTOMATION_LAMBDA: config.backupFunction || "",
        UPGRADE_AUTOMATION_LAMBDA: config.upgradeFunction || "",
        TARGETS_TABLE: props.dynamodbTable || "",
        LAMBDA_INVOCATION_TYPE: this.DEFAULT_LAMBDA_INVOCATION_TYPE,
        LAMBDA_LOG_TYPE: this.DEFAULT_LOG_TYPE,
        POWERTOOLS_LOGGER_LOG_EVENT: "true",
        POWERTOOLS_LOG_LEVEL: "INFO",
      },
    });
  }

  createRestApi(props: RestApiConstructProps): RestApi {
    const apiRole: Role = this.apiRole(props);
    const api: RestApi = new RestApi(this, "RestApi", {
      restApiName: props.config.restApiName,
    });

    this.addRoutes(api, apiRole, props);

    // this.deployRestApi(api);

    return api;
  }

  apiRole(props: RestApiConstructProps): Role {
    const restApiConfig: LambdaRestApi = props.config;

    const role: Role = new Role(this, "ApiGatewayRole", {
      assumedBy: new ServicePrincipal("apigateway.amazonaws.com"),
      roleName: restApiConfig.apiRoleName,
      description: "Allows API Gateway to invoke lamda function",
    });

    role.addManagedPolicy(
      ManagedPolicy.fromManagedPolicyArn(
        this,
        "AmazonAPIGatewayPushToCloudWatchLogs",
        "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs",
      ),
    );

    role.addToPolicy(
      new PolicyStatement({
        sid: "InvokeLambda",
        actions: ["lambda:InvokeFunction"],
        resources: [this.function.functionArn],
      }),
    );

    return role;
  }

  addRoutes(api: RestApi, apiRole: Role, props: RestApiConstructProps) {
    const lambdaIntegration: LambdaIntegration = new LambdaIntegration(
      this.function,
      {
        proxy: true,
        credentialsRole: apiRole,
      },
    );

    // Put tenants/onboard
    const tenants: Resource = api.root.addResource("tenants");
    const onboard: Resource = tenants.addResource("onboard");
    onboard.addMethod(HttpMethod.PUT, lambdaIntegration, {
      requestModels: {
        "application/json": this.getTenantOnboardingRequest(api),
      },
      methodResponses: [
        this.getTenantOnboardingResponse(api, "TenantOnboardingResponse"),
        this.getErrorLambdaResponse(api, "TenantOnboardingErrorResponse"),
      ],
    });

    // GET /clusters
    const clusters: Resource = api.root.addResource("clusters");
    clusters.addMethod(HttpMethod.GET, lambdaIntegration, {
      requestParameters: {
        "method.request.querystring.AccountId": false,
        "method.request.querystring.Region": false,
        "method.request.querystring.ClusterName": false,
        "method.request.querystring.ReportDate": false,
        "method.request.querystring.Information": false,
        "method.request.querystring.QueryCache": false,
        "method.request.querystring.InformationRelativeDate": false,
      },
      methodResponses: [this.getClusterResponse(api)],
    });

    // GET/clusters/{execution_id}
    const ssmExecution: Resource = clusters.addResource("{execution_id}");
    ssmExecution.addMethod(HttpMethod.GET, lambdaIntegration, {
      methodResponses: [this.getSSMStatusResponse(api)],
    });

    if (props.summaryEnabled) {
      const summary: Resource = clusters.addResource("summary");
      // POST /clusters/summary
      summary.addMethod(HttpMethod.POST, lambdaIntegration, {
        requestModels: {
          "application/json": this.getSummaryRequest(api),
        },
        methodResponses: [
          this.getLambdaResponse(api, "SummaryLambdaResponse"),
          this.getErrorLambdaResponse(api, "ErrorSummaryLambdaResponse"),
        ],
      });
    }

    if (props.backupEnabled) {
      // POST /clusters/backup
      const backup: Resource = clusters.addResource("backup");
      backup.addMethod(HttpMethod.POST, lambdaIntegration, {
        requestModels: {
          "application/json": this.getBackupRequest(api),
        },
        methodResponses: [
          this.getLambdaResponse(api, "BackupLambdaResponse"),
          this.getErrorLambdaResponse(api, "ErrorBackupLambdaResponse"),
        ],
      });

      // POST /clusters/restore
      const restore: Resource = clusters.addResource("restore");
      restore.addMethod(HttpMethod.POST, lambdaIntegration, {
        requestModels: {
          "application/json": this.getRestoreRequest(api),
        },
        methodResponses: [
          this.getLambdaResponse(api, "RestoreLambdaResponse"),
          this.getErrorLambdaResponse(api, "ErrorRestoreLambdaResponse"),
        ],
      });
    }

    if (props.upgradeEnabled) {
      // PATCH /clusters/upgrade
      const upgrade: Resource = clusters.addResource("upgrade");
      upgrade.addMethod(HttpMethod.PATCH, lambdaIntegration, {
        requestModels: {
          "application/json": this.getUpgradeRequest(api),
        },
        methodResponses: [
          this.getLambdaResponse(api, "UpgradeLambdaResponse"),
          this.getErrorLambdaResponse(api, "ErrorUpgradeLambdaResponse"),
        ],
      });
    }
  }

  deployRestApi(api: RestApi): Stage {
    const deployment = new Deployment(this, "RestApiDeployment", { api });

    const logGroup: LogGroup = new LogGroup(this, "ApiLogs");

    return new Stage(this, "api", {
      deployment,
      accessLogDestination: new LogGroupLogDestination(logGroup),
      accessLogFormat: AccessLogFormat.jsonWithStandardFields({
        caller: true,
        httpMethod: true,
        ip: true,
        protocol: true,
        requestTime: true,
        resourcePath: true,
        responseLength: true,
        status: true,
        user: true,
      }),
    });
  }

  getTenantOnboardingRequest(api: RestApi) {
    return new Model(this, "TenantOnboardingRequest", {
      restApi: api,
      contentType: "application/json",
      modelName: "TenantOnboardingRequest",
      description: "Request schema for PUT /tenants/onboard",
      schema: {
        schema: JsonSchemaVersion.DRAFT7,
        title: "tenantOnboardingRequest",
        type: JsonSchemaType.OBJECT,
        properties: {
          Tenants: {
            type: JsonSchemaType.ARRAY,
            items: {
              type: JsonSchemaType.OBJECT,
              properties: {
                AccountId: { type: JsonSchemaType.STRING },
                Region: { type: JsonSchemaType.STRING },
                ExecutionRoleName: { type: JsonSchemaType.STRING },
              },
            },
          },
        },
      },
    });
  }

  getSummaryRequest(api: RestApi) {
    return new Model(this, "ClusterSummaryRequest", {
      restApi: api,
      contentType: "application/json",
      modelName: "ClusterSummaryRequest",
      description: "Request schema for GET /clusters/summary",
      schema: {
        schema: JsonSchemaVersion.DRAFT7,
        title: "clusterSummaryRequest",
        type: JsonSchemaType.OBJECT,
        properties: {
          Clusters: {
            type: JsonSchemaType.OBJECT,
            required: ["Summary"],
            properties: {
              Summary: {
                type: JsonSchemaType.ARRAY,
                items: {
                  type: JsonSchemaType.OBJECT,
                  required: ["AccountId", "Region", "ClusterName"],
                  properties: {
                    AccountId: {
                      type: JsonSchemaType.STRING,
                    },
                    Region: {
                      type: JsonSchemaType.STRING,
                    },
                    ClusterName: {
                      type: JsonSchemaType.STRING,
                    },
                  },
                },
              },
            },
          },
        },
      },
    });
  }

  getBackupRequest(api: RestApi): Model {
    return new Model(this, "ClusterBackUpRequest", {
      restApi: api,
      contentType: "application/json",
      modelName: "ClusterBackUpRequest",
      description: "Request schema for GET /clusters/backup",
      schema: {
        schema: JsonSchemaVersion.DRAFT7,
        title: "clusterBackUpRequest",
        type: JsonSchemaType.OBJECT,
        properties: {
          Clusters: {
            type: JsonSchemaType.OBJECT,
            required: ["Backup"],
            properties: {
              Backup: {
                type: JsonSchemaType.ARRAY,
                items: {
                  type: JsonSchemaType.OBJECT,
                  required: ["AccountId", "Region", "ClusterName"],
                  properties: {
                    AccountId: {
                      type: JsonSchemaType.STRING,
                    },
                    Region: {
                      type: JsonSchemaType.STRING,
                    },
                    ClusterName: {
                      type: JsonSchemaType.STRING,
                    },
                    BackupOptions: {
                      type: JsonSchemaType.OBJECT,
                      properties: {
                        BackupName: {
                          type: JsonSchemaType.STRING,
                          description:
                            "Name of the velero backup to be created",
                        },
                      },
                    },
                  },
                },
              },
            },
          },
        },
      },
    });
  }

  getRestoreRequest(api: RestApi): Model {
    return new Model(this, "ClusterRestoreRequest", {
      restApi: api,
      contentType: "application/json",
      modelName: "ClusterRestoreRequest",
      description: "Request schema for GET /clusters/restore",
      schema: {
        schema: JsonSchemaVersion.DRAFT7,
        title: "clusterRestoreRequest",
        type: JsonSchemaType.OBJECT,
        properties: {
          Clusters: {
            type: JsonSchemaType.OBJECT,
            required: ["Restore"],
            properties: {
              Restore: {
                type: JsonSchemaType.ARRAY,
                items: {
                  type: JsonSchemaType.OBJECT,
                  required: [
                    "AccountId",
                    "Region",
                    "ClusterName",
                    "RestoreOptions",
                    "BackupName",
                  ],
                  properties: {
                    AccountId: {
                      type: JsonSchemaType.STRING,
                    },
                    Region: {
                      type: JsonSchemaType.STRING,
                    },
                    ClusterName: {
                      type: JsonSchemaType.STRING,
                    },
                    RestoreOptions: {
                      type: JsonSchemaType.OBJECT,
                      properties: {
                        BackupName: {
                          type: JsonSchemaType.STRING,
                          description:
                            "Name of the velero backup which needs to be restored",
                        },
                      },
                    },
                  },
                },
              },
            },
          },
        },
      },
    });
  }

  getUpgradeRequest(api: RestApi): Model {
    return new Model(this, "ClusterUpgradeRequest", {
      restApi: api,
      contentType: "application/json",
      modelName: "ClusterUpgradeRequest",
      description: "Request schema for GET /clusters/upgrade",
      schema: {
        schema: JsonSchemaVersion.DRAFT7,
        title: "clusterUpgradeRequest",
        type: JsonSchemaType.OBJECT,
        properties: {
          Clusters: {
            type: JsonSchemaType.OBJECT,
            required: ["Upgrade"],
            properties: {
              Upgrade: {
                type: JsonSchemaType.ARRAY,
                items: {
                  type: JsonSchemaType.OBJECT,
                  required: [
                    "AccountId",
                    "Region",
                    "ClusterName",
                    "UpgradeOptions",
                    "DesiredEKSVersion",
                  ],
                  properties: {
                    AccountId: {
                      type: JsonSchemaType.STRING,
                    },
                    Region: {
                      type: JsonSchemaType.STRING,
                    },
                    ClusterName: {
                      type: JsonSchemaType.STRING,
                    },
                    UpgradeOptions: {
                      type: JsonSchemaType.OBJECT,
                      properties: {
                        DesiredEKSVersion: {
                          type: JsonSchemaType.STRING,
                          description:
                            "EKS Version to upgrade to. This should be the next minor version",
                        },
                      },
                    },
                  },
                },
              },
            },
          },
        },
      },
    });
  }

  getTenantOnboardingResponse(api: RestApi, id: string): MethodResponse {
    const model: Model = new Model(this, id, {
      restApi: api,
      contentType: "application/json",
      modelName: id,
      description: "Response schema for PUT /tenant/onboard",
      schema: {
        schema: JsonSchemaVersion.DRAFT7,
        title: "tenantOnboardingResponse",
        type: JsonSchemaType.OBJECT,
        properties: {
          StatusCode: {
            type: JsonSchemaType.NUMBER,
            description: "HTTP status code",
          },
          Request: {
            type: JsonSchemaType.ARRAY,
          },
          Response: {
            type: JsonSchemaType.OBJECT,
            properties: {
              InsertedRecords: {
                type: JsonSchemaType.ARRAY,
              },
              PutBucketPolicy: {
                type: JsonSchemaType.OBJECT,
              },
            },
          },
        },
      },
    });

    return {
      statusCode: "202",
      responseParameters: {
        "method.response.header.Content-Type": true,
        "method.response.header.Content-Length": false,
      },
      responseModels: {
        "application/json": model,
      },
    };
  }

  getClusterResponse(api: RestApi): MethodResponse {
    const model: Model = new Model(this, "ClusterResponse", {
      restApi: api,
      contentType: "application/json",
      modelName: "ClusterResponse",
      description: "Response schema for GET /clusters",
      schema: {
        schema: JsonSchemaVersion.DRAFT7,
        title: "clusterResponse",
        type: JsonSchemaType.OBJECT,
        properties: {
          StatusCode: {
            type: JsonSchemaType.NUMBER,
            description: "HTTP status code",
          },
          Request: {
            type: JsonSchemaType.OBJECT,
            properties: {
              AccountId: {
                type: JsonSchemaType.STRING,
                description: "12 digit AWS Account ID",
              },
              Region: {
                type: JsonSchemaType.STRING,
                description: "AWS Region",
              },
              ClusterName: {
                type: JsonSchemaType.STRING,
                description: "EKS Cluster name",
              },
              ReportDate: {
                type: JsonSchemaType.STRING,
                description:
                  "Date for which data was fetched from athena tables",
              },
              QueryCache: {
                type: JsonSchemaType.BOOLEAN,
                description:
                  "Specifies weather the result was fetched from cache",
              },
              Information: {
                type: JsonSchemaType.STRING,
                description:
                  "Type of response details to return. Defaulted to Metadata",
              },
              InformationRelativeDate: {
                type: JsonSchemaType.BOOLEAN,
                description:
                  "Specifies weather the data was fetched from the metadata table or `Information` table",
              },
            },
          },
          Response: {
            type: JsonSchemaType.OBJECT,
            properties: {
              Clusters: {
                type: JsonSchemaType.ARRAY,
                items: {
                  type: JsonSchemaType.OBJECT,
                  properties: {
                    AccountId: {
                      type: JsonSchemaType.STRING,
                      description: "12 digit AWS Account ID",
                    },
                    Region: {
                      type: JsonSchemaType.STRING,
                      description: "AWS Region",
                    },
                    ClusterName: {
                      type: JsonSchemaType.STRING,
                      description: "EKS Cluster name",
                    },
                    ReportDate: {
                      type: JsonSchemaType.STRING,
                      description:
                        "Date for which data was fetched from athena tables",
                    },
                    Details: {
                      type: JsonSchemaType.OBJECT,
                      properties: {
                        Metadata: {
                          type: JsonSchemaType.OBJECT,
                          description: "Metadata information about the cluster",
                        },
                        DeprecatedApis: {
                          type: JsonSchemaType.ARRAY,
                          items: {
                            type: JsonSchemaType.OBJECT,
                          },
                          description:
                            "Deprecated API details present in the cluster",
                        },
                        CertificateSigningRequest: {
                          type: JsonSchemaType.ARRAY,
                          items: {
                            type: JsonSchemaType.OBJECT,
                          },
                          description:
                            "Customer signing requests present in the cluster",
                        },
                        PodSecurityPolicies: {
                          type: JsonSchemaType.ARRAY,
                          items: {
                            type: JsonSchemaType.OBJECT,
                          },
                          description:
                            "Pod security policies present in the cluster",
                        },
                        UnhealthyPods: {
                          type: JsonSchemaType.ARRAY,
                          items: {
                            type: JsonSchemaType.OBJECT,
                          },
                          description: "Unhealthy pods present in the cluster",
                        },
                        SingletonResources: {
                          type: JsonSchemaType.ARRAY,
                          items: {
                            type: JsonSchemaType.OBJECT,
                          },
                          description:
                            "Singleton deployments and statefulsets present in the cluster",
                        },
                        Addons: {
                          type: JsonSchemaType.ARRAY,
                          items: {
                            type: JsonSchemaType.OBJECT,
                          },
                          description: "Addon details attached to the cluster",
                        },
                        Backup: {
                          type: JsonSchemaType.OBJECT,
                          description: "Velero backup object details",
                        },
                        Restore: {
                          type: JsonSchemaType.OBJECT,
                          description: "Velero restore object details",
                        },
                        Upgrade: {
                          type: JsonSchemaType.OBJECT,
                          description:
                            "Upgrade details for control plane, addons and nodegroups",
                        },
                      },
                    },
                  },
                },
              },
            },
          },
        },
      },
    });

    return {
      statusCode: "200",
      responseParameters: {
        "method.response.header.Content-Type": true,
        "method.response.header.Content-Length": false,
      },
      responseModels: {
        "application/json": model,
      },
    };
  }

  getSSMStatusResponse(api: RestApi): MethodResponse {
    const model: Model = new Model(this, "SSMStatusResponse", {
      restApi: api,
      contentType: "application/json",
      modelName: "SSMStatusResponse",
      description: "Response schema for GET /clusters/{execution_id}",
      schema: {
        schema: JsonSchemaVersion.DRAFT7,
        title: "ssmStatusResponse",
        type: JsonSchemaType.OBJECT,
        properties: {
          StatusCode: {
            type: JsonSchemaType.NUMBER,
            description: "HTTP status code",
          },
          Response: {
            type: JsonSchemaType.OBJECT,
            properties: {
              ExecutionId: {
                type: JsonSchemaType.STRING,
                description: "SSM Execution Id",
              },
              DocumentName: {
                type: JsonSchemaType.STRING,
                description: "SSM Automation document name",
              },
              Status: {
                type: JsonSchemaType.STRING,
                description: "SSM Automation status",
              },
              StartTime: {
                type: JsonSchemaType.STRING,
                description: "SSM Automation start time",
              },
              EndTime: {
                type: JsonSchemaType.STRING,
                description:
                  "SSM Automation end time. Will be null if automation is still In Progress state",
              },
              Progress: {
                type: JsonSchemaType.OBJECT,
                properties: {
                  TotalSteps: {
                    type: JsonSchemaType.NUMBER,
                    description: "Total number of steps to execute",
                  },
                  SuccessSteps: {
                    type: JsonSchemaType.NUMBER,
                    description:
                      "Number of steps that were successfully completed",
                  },
                  FailedSteps: {
                    type: JsonSchemaType.NUMBER,
                    description: "Number of steps that failed",
                  },
                  CancelledSteps: {
                    type: JsonSchemaType.NUMBER,
                    description: "Number of steps that were cancelled",
                  },
                  TimedOutSteps: {
                    type: JsonSchemaType.NUMBER,
                    description: "Number of steps that timed out",
                  },
                },
              },
              TargetLocations: {
                type: JsonSchemaType.ARRAY,
                items: {
                  type: JsonSchemaType.OBJECT,
                  properties: {
                    Accounts: {
                      type: JsonSchemaType.ARRAY,
                      items: {
                        type: JsonSchemaType.STRING,
                      },
                    },
                    Regions: {
                      type: JsonSchemaType.ARRAY,
                      items: {
                        type: JsonSchemaType.STRING,
                      },
                    },
                    TargetLocationMaxConcurrency: {
                      type: JsonSchemaType.STRING,
                      description:
                        "The maximum number of AWS Regions and AWS accounts allowed to run the Automation concurrently",
                    },
                    TargetLocationMaxErrors: {
                      type: JsonSchemaType.STRING,
                      description:
                        "The maximum number of errors allowed before the system stops queueing additional Automation executions for the currently running Automation",
                    },
                  },
                },
              },
              ExecutionRoleName: {
                type: JsonSchemaType.STRING,
                description:
                  "IAM role used in the target account to start the automation",
              },
              StepExecutions: {
                type: JsonSchemaType.ARRAY,
                description: "Steps execution details",
                items: {
                  type: JsonSchemaType.OBJECT,
                  properties: {
                    Name: {
                      type: JsonSchemaType.STRING,
                      description: "Name of the Step",
                    },
                    Status: {
                      type: JsonSchemaType.STRING,
                      description: "Status of the step execution",
                    },
                    StepExecutionId: {
                      type: JsonSchemaType.STRING,
                      description: "Step execution ID",
                    },
                  },
                },
              },
            },
          },
        },
      },
    });

    return {
      statusCode: "200",
      responseParameters: {
        "method.response.header.Content-Type": true,
        "method.response.header.Content-Length": false,
      },
      responseModels: {
        "application/json": model,
      },
    };
  }

  getLambdaResponse(api: RestApi, id: string): MethodResponse {
    const model: Model = new Model(this, id, {
      restApi: api,
      contentType: "application/json",
      modelName: id,
      description:
        "Response schema for GET /clusters/[summary, backup, restore, upgrade]",
      schema: {
        schema: JsonSchemaVersion.DRAFT7,
        title: "lambdaResponse",
        type: JsonSchemaType.OBJECT,
        properties: {
          StatusCode: {
            type: JsonSchemaType.NUMBER,
            description: "HTTP status code",
          },
          Request: {
            type: JsonSchemaType.OBJECT,
            properties: {
              TargetLocations: {
                type: JsonSchemaType.ARRAY,
                items: {
                  type: JsonSchemaType.OBJECT,
                  properties: {
                    Accounts: {
                      type: JsonSchemaType.ARRAY,
                      items: {
                        type: JsonSchemaType.STRING,
                      },
                    },
                    Regions: {
                      type: JsonSchemaType.ARRAY,
                      items: {
                        type: JsonSchemaType.STRING,
                      },
                    },
                    ExecutionRoleName: {
                      type: JsonSchemaType.STRING,
                    },
                  },
                },
              },
              Parameters: {
                type: JsonSchemaType.OBJECT,
                properties: {
                  AssumeRole: {
                    type: JsonSchemaType.ARRAY,
                    items: {
                      type: JsonSchemaType.STRING,
                    },
                  },
                  S3Bucket: {
                    type: JsonSchemaType.ARRAY,
                    items: {
                      type: JsonSchemaType.STRING,
                    },
                  },
                  S3OutputLogsPrefix: {
                    type: JsonSchemaType.ARRAY,
                    items: {
                      type: JsonSchemaType.STRING,
                    },
                  },
                  ExecutionTimeout: {
                    type: JsonSchemaType.ARRAY,
                    items: {
                      type: JsonSchemaType.STRING,
                    },
                  },
                },
              },
              MaxConcurrency: {
                type: JsonSchemaType.NUMBER,
              },
              MaxErrors: {
                type: JsonSchemaType.NUMBER,
              },
            },
          },
          Response: {
            type: JsonSchemaType.OBJECT,
            properties: {
              AutomationExecutionId: {
                type: JsonSchemaType.STRING,
                description: "ID of the SSM automation execution",
              },
            },
          },
        },
      },
    });

    return {
      statusCode: "202",
      responseParameters: {
        "method.response.header.Content-Type": true,
        "method.response.header.Content-Length": false,
      },
      responseModels: {
        "application/json": model,
      },
    };
  }

  getErrorLambdaResponse(api: RestApi, id: string): MethodResponse {
    const model: Model = new Model(this, id, {
      restApi: api,
      contentType: "application/json",
      modelName: id,
      description:
        "Error response schema for GET /clusters/[summary, backup, restore, upgrade]",
      schema: {
        schema: JsonSchemaVersion.DRAFT7,
        title: "errorLambdaResponse",
        type: JsonSchemaType.OBJECT,
        properties: {
          StatusCode: {
            type: JsonSchemaType.NUMBER,
            description: "HTTP status code",
          },
          Response: {
            type: JsonSchemaType.OBJECT,
            properties: {
              Error: {
                type: JsonSchemaType.OBJECT,
                properties: {
                  Message: {
                    type: JsonSchemaType.STRING,
                  },
                },
              },
            },
          },
        },
      },
    });

    return {
      statusCode: "500",
      responseParameters: {
        "method.response.header.Content-Type": true,
        "method.response.header.Content-Length": false,
      },
      responseModels: {
        "application/json": model,
      },
    };
  }
}
