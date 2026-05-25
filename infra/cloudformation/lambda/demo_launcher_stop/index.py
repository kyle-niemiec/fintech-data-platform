import json
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

INSTANCE_ID = os.environ["INSTANCE_ID"]
EC2 = boto3.client("ec2")


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """
    Main Lambda handler function to stop the EC2 instance when invoked.
    """
    del event

    try:
        # Stop the EC2 instance using the provided INSTANCE_ID environment variable
        EC2.stop_instances(InstanceIds=[INSTANCE_ID])

        return {
            "statusCode": 200,
            "body": json.dumps({"instance_id": INSTANCE_ID, "stop_requested": True}),
        }
    except ClientError as exc:
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "message": "aws_client_error",
                    "detail": exc.response.get("Error", {}).get("Message", str(exc)),
                }
            ),
        }
