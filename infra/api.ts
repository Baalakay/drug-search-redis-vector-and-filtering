/// <reference path="../.sst/platform/config.d.ts" />

/**
 * API Infrastructure
 * 
 * Defines API Gateway with Lambda functions for application endpoints.
 * 
 * CRITICAL: Uses sst.aws.Function (NOT raw Pulumi aws.lambda.Function)
 * See: docs/SST_UV_RECURRING_ISSUES.md #5
 */

import * as aws from "@pulumi/aws";
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
        Project: $app.name,
        Environment: stage
    }
});

/**
 * API Gateway Stage with Access Logging
 */
const apiAccessLogs = new aws.cloudwatch.LogGroup("DAW-SearchAPI-AccessLogs", {
    name: `/aws/apigateway/${$app.name}-SearchAPI-${stage}`,
    retentionInDays: 7,
    tags: {
        Name: `${$app.name}-SearchAPI-AccessLogs-${stage}`,
        Project: $app.name
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
        Name: `${$app.name}-SearchAPI-Stage-${stage}`,
        Project: $app.name,
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
