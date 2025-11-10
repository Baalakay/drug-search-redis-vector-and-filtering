"""
Lambda function to stop/start EC2 instances based on tags
Triggered by EventBridge on a schedule

Environment Variables:
- ACTION: 'stop' or 'start'
- TAG_KEY: Tag key to filter instances (default: 'AutoShutdown')
- TAG_VALUE: Tag value to filter instances (default: 'Enabled')
"""

import boto3
import os
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    """
    Stop or start EC2 instances based on tags
    """
    # Get configuration from event (passed by EventBridge) or environment variables
    action = event.get('ACTION', os.environ.get('ACTION', '')).lower()
    tag_key = event.get('TAG_KEY', os.environ.get('TAG_KEY', 'AutoShutdown'))
    tag_value = event.get('TAG_VALUE', os.environ.get('TAG_VALUE', 'Enabled'))
    
    if action not in ['stop', 'start']:
        logger.error(f"Invalid ACTION: {action}. Must be 'stop' or 'start'")
        return {
            'statusCode': 400,
            'body': f'Invalid ACTION: {action}'
        }
    
    logger.info(f"Action: {action}, Tag: {tag_key}={tag_value}")
    
    try:
        # Find instances with the specified tag
        if action == 'stop':
            # Only target running instances for stop
            filters = [
                {'Name': f'tag:{tag_key}', 'Values': [tag_value]},
                {'Name': 'instance-state-name', 'Values': ['running']}
            ]
        else:
            # Only target stopped instances for start
            filters = [
                {'Name': f'tag:{tag_key}', 'Values': [tag_value]},
                {'Name': 'instance-state-name', 'Values': ['stopped']}
            ]
        
        response = ec2.describe_instances(Filters=filters)
        
        instance_ids = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_ids.append(instance['InstanceId'])
                logger.info(f"Found instance: {instance['InstanceId']} ({instance.get('Tags', [])})")
        
        if not instance_ids:
            logger.info(f"No instances found with tag {tag_key}={tag_value} in appropriate state")
            return {
                'statusCode': 200,
                'body': f'No instances to {action}'
            }
        
        # Perform the action
        if action == 'stop':
            logger.info(f"Stopping instances: {instance_ids}")
            ec2.stop_instances(InstanceIds=instance_ids)
            message = f'Successfully stopped {len(instance_ids)} instance(s): {instance_ids}'
        else:
            logger.info(f"Starting instances: {instance_ids}")
            ec2.start_instances(InstanceIds=instance_ids)
            message = f'Successfully started {len(instance_ids)} instance(s): {instance_ids}'
        
        logger.info(message)
        return {
            'statusCode': 200,
            'body': message
        }
        
    except Exception as e:
        logger.error(f"Error {action}ing instances: {str(e)}")
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }

