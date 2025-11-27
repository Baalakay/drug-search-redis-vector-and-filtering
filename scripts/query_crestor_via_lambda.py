#!/usr/bin/env python3
"""
Query Crestor data by invoking the DrugSync Lambda which has DB access
"""
import boto3
import json

lambda_client = boto3.client('lambda', region_name='us-east-1')

# Create a custom query payload
payload = {
    "action": "query_crestor_data"
}

response = lambda_client.invoke(
    FunctionName='DAW-DrugSync-dev',
    InvocationType='RequestResponse',
    Payload=json.dumps(payload)
)

result = json.loads(response['Payload'].read())
print(json.dumps(result, indent=2))

