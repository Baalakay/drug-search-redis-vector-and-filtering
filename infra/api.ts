/**
 * API Infrastructure - Drug Search API
 * 
 * Defines API Gateway and Lambda functions for:
 * - POST /search - Natural language drug search  
 * - GET /drugs/{ndc}/alternatives - Therapeutic equivalents
 * - GET /drugs/{ndc} - Drug details
 * 
 * CRITICAL: Uses sst.aws.Function (NOT raw Pulumi aws.lambda.Function)
 * See: docs/SST_UV_RECURRING_ISSUES.md #5
 */

import * as pulumi from "@pulumi/pulumi";

const config = new pulumi.Config();
const stage = pulumi.getStack();

/**
 * IMPORTANT: This file uses Pulumi for API Gateway setup.
 * Lambda functions should be defined using sst.aws.Function in sst.config.ts
 * 
 * See docs/SST_LAMBDA_MIGRATION_COMPLETE_GUIDE.md for correct patterns.
 */

/**
 * API Gateway HTTP API
 */
export const api = new aws.apigatewayv2.Api("DAW-SearchAPI", {
    protocolType: "HTTP",
    corsConfiguration: {
        allowOrigins: ["*"], // Configure based on frontend domain
        allowMethods: ["GET", "POST", "OPTIONS"],
        allowHeaders: ["Content-Type", "Authorization"],
        maxAge: 3600
    },
    tags: {
        Name: `DAW-SearchAPI-${stage}`,
        Project: "DAW",
        Environment: stage
    }
});

/**
 * API Gateway Stage with Access Logging
 */
const apiAccessLogs = new aws.cloudwatch.LogGroup("DAW-SearchAPI-AccessLogs", {
    name: `/aws/apigateway/DAW-SearchAPI-${stage}`,
    retentionInDays: 7,
    tags: {
        Name: `DAW-SearchAPI-AccessLogs-${stage}`,
        Project: "DAW"
    }
});

export const apiStage = new aws.apigatewayv2.Stage("DAW-SearchAPI-Stage", {
    apiId: api.id,
    name: stage,
    autoDeploy: true,
    accessLogSettings: {
        destinationArn: apiAccessLogs.arn,
        format: JSON.stringify({
            requestId: "$context.requestId",
            ip: "$context.identity.sourceIp",
            requestTime: "$context.requestTime",
            httpMethod: "$context.httpMethod",
            routeKey: "$context.routeKey",
            status: "$context.status",
            protocol: "$context.protocol",
            responseLength: "$context.responseLength",
            integrationLatency: "$context.integrationLatency",
            responseLatency: "$context.responseLatency"
        })
    },
    tags: {
        Name: `DAW-SearchAPI-Stage-${stage}`,
        Project: "DAW",
        Environment: stage
    }
});

/**
 * Lambda Functions and API Routes
 * 
 * These are defined in sst.config.ts using sst.aws.Function
 * This file only exports the API Gateway for integration
 */

/**
 * Exports
 */
export const apiUrl = pulumi.interpolate`${api.apiEndpoint}/${stage}`;
export const apiId = api.id;
