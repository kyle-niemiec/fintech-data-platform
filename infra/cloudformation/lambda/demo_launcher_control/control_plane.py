import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import boto3

INSTANCE_ID = os.environ["INSTANCE_ID"]
STOP_FUNCTION_ARN = os.environ["STOP_FUNCTION_ARN"]
SCHEDULER_ROLE_ARN = os.environ["SCHEDULER_ROLE_ARN"]
SCHEDULE_GROUP = os.environ.get("SCHEDULE_GROUP", "default")
SCHEDULE_NAME = os.environ.get("SCHEDULE_NAME", f"meridian-demo-stop-{INSTANCE_ID}")
DEFAULT_TTL_MINUTES = int(os.environ.get("DEFAULT_TTL_MINUTES", "30"))
APP_HEALTH_URL = os.environ.get("APP_HEALTH_URL", "").strip()

EC2 = boto3.client("ec2")
SCHEDULER = boto3.client("scheduler")


def json_response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Helper to format a JSON response for API Gateway.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "content-type": "application/json",
        },
        "body": json.dumps(payload),
    }


def instance_state() -> str:
    """
    Retrieves the current state of the EC2 instance.
    """
    response = EC2.describe_instances(InstanceIds=[INSTANCE_ID])
    return response["Reservations"][0]["Instances"][0]["State"]["Name"]


def get_schedule() -> dict[str, Any] | None:
    """
    Retrieves the schedule information for the EC2 instance.
    """
    try:
        return SCHEDULER.get_schedule(Name=SCHEDULE_NAME, GroupName=SCHEDULE_GROUP)
    except SCHEDULER.exceptions.ResourceNotFoundException:
        return None


def extract_stop_timestamp(schedule_expression: str | None) -> str | None:
    """
    Extracts the stop timestamp from the schedule expression if it is in the expected "at(...)" format.
    """
    if not schedule_expression:
        return None

    is_formatted = schedule_expression.startswith("at(") and schedule_expression.endswith(")")

    if not is_formatted:
        return None

    value = schedule_expression[3:-1]

    if not value:
        return None

    # Scheduler "at" is UTC by contract; append explicit marker for clients.
    return f"{value}Z"


def schedule_stop_once(stop_at: datetime) -> None:
    """
    Schedule the EC2 instance to be stopped after running for the configured TTL.
    """
    expression = stop_at.strftime("at(%Y-%m-%dT%H:%M:%S)")

    try:
        SCHEDULER.create_schedule(
            Name=SCHEDULE_NAME,
            GroupName=SCHEDULE_GROUP,
            ScheduleExpression=expression,
            FlexibleTimeWindow={"Mode": "OFF"},
            State="ENABLED",
            ActionAfterCompletion="DELETE",
            Target={
                "Arn": STOP_FUNCTION_ARN,
                "RoleArn": SCHEDULER_ROLE_ARN,
                "Input": json.dumps(
                    {
                        "instance_id": INSTANCE_ID,
                        "trigger": "demo_ttl",
                    }
                ),
            },
        )
    except SCHEDULER.exceptions.ConflictException:
        # Existing schedule means there is already an active window. Do not extend it.
        return


def app_ready(current_state: str) -> bool:
    """
    Checks if the application is ready by verifying the instance state and
    optionally an application health endpoint.
    """
    if current_state != "running":
        return False

    # Check app health endpoint if configured
    if not APP_HEALTH_URL:
        return True

    request = Request(APP_HEALTH_URL, method="GET")

    try:
        with urlopen(request, timeout=3) as response:
            return 200 <= response.status < 400
    except URLError:
        return False


def status_payload(current_state: str) -> dict[str, Any]:
    """
    Constructs the payload for the status response, including instance state,
    scheduled stop time, and app readiness.
    """
    schedule = get_schedule()

    stop_at = extract_stop_timestamp(
        schedule.get("ScheduleExpression") if schedule else None
    )

    return {
        "instance_id": INSTANCE_ID,
        "instance_state": current_state,
        "stop_scheduled_at": stop_at,
        "app_ready": app_ready(current_state),
    }


def handle_start() -> dict[str, Any]:
    """
    Handles the logic for starting the EC2 instance, including scheduling a stop
    time and constructing the response payload.
    """
    state = instance_state()
    did_request_start = False

    if state == "stopped":
        EC2.start_instances(InstanceIds=[INSTANCE_ID])
        did_request_start = True
        state = "pending"
        stop_at = datetime.now(timezone.utc) + timedelta(minutes=DEFAULT_TTL_MINUTES)
        schedule_stop_once(stop_at)

    payload = status_payload(state)
    payload["start_requested"] = did_request_start
    return json_response(202, payload)
