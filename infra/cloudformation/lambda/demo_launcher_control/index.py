from typing import Any

from botocore.exceptions import ClientError

from control_plane import handle_start, instance_state, json_response, status_payload


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """
    Main Lambda handler function to route incoming API Gateway requests to the
    appropriate logic based on HTTP method and path.
    """
    method = (
        event.get("requestContext", {})
        .get("http", {})
        .get("method", "")
        .upper()
    )

    raw_path = event.get("rawPath", "")

    try:
        # Route: POST /start - Start the instance if it is stopped and schedule a stop time.
        if method == "POST" and raw_path == "/start":
            return handle_start()

        # Route: GET /status - Retrieve the current status of the instance, including state, scheduled stop time, and app readiness.
        if method == "GET" and raw_path == "/status":
            return json_response(200, status_payload(instance_state()))

        # Route not found
        return json_response(
            404,
            {
                "message": "not found",
                "supported_routes": ["POST /start", "GET /status"],
            },
        )
    except ClientError as exc:
        return json_response(
            500,
            {
                "message": "aws_client_error",
                "detail": exc.response.get("Error", {}).get("Message", str(exc)),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive
        return json_response(500, {"message": "internal_error", "detail": str(exc)})
