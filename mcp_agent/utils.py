import json
import logging
from typing import Any, Dict, List, Optional, Union

from google.api_core import exceptions as google_exceptions
from mcp import types as mcp_types

logger = logging.getLogger(__name__)

def format_response(
    status: str, message: str, data: Optional[Dict[str, Any]] = None
) -> List[mcp_types.TextContent]:
    """Formats a standard JSON response within MCP TextContent."""
    payload = {"status": status, "message": message}
    if data is not None:
        payload["data"] = data
    try:
        # Attempt to serialize data cleanly
        json_string = json.dumps(payload, default=str) # Use default=str for non-serializable types like datetime
    except TypeError as e:
        logger.error(f"JSON serialization error: {e}. Payload: {payload}")
        # Fallback for unexpected serialization issues
        payload = {
            "status": "error",
            "message": f"Internal server error during response serialization: {e}",
        }
        json_string = json.dumps(payload)

    return [mcp_types.TextContent(type="text", text=json_string)]

def format_success(
    message: str, data: Optional[Dict[str, Any]] = None
) -> List[mcp_types.TextContent]:
    """Helper for successful responses."""
    return format_response("success", message, data)

def format_error(
    message: str, data: Optional[Dict[str, Any]] = None
) -> List[mcp_types.TextContent]:
    """Helper for error responses."""
    logger.warning(f"Operation resulted in error: {message}" + (f" Data: {data}" if data else ""))
    return format_response("error", message, data)

def format_info(
     message: str, data: Optional[Dict[str, Any]] = None
) -> List[mcp_types.TextContent]:
    """Helper for informational responses."""
    return format_response("info", message, data)

def handle_gcp_error(
    e: Exception, operation_description: str
) -> List[mcp_types.TextContent]:
    """Handles common GCP exceptions and formats an error response."""
    error_message = f"An unexpected error occurred during {operation_description}: {type(e).__name__}: {e}"
    details = {"exception_type": type(e).__name__, "exception_details": str(e)}

    if isinstance(e, google_exceptions.NotFound):
        error_message = f"Resource not found during {operation_description}: {e}"
    elif isinstance(e, google_exceptions.Forbidden):
        error_message = f"Permission denied during {operation_description}. Check server credentials/permissions: {e}"
    elif isinstance(e, google_exceptions.InvalidArgument):
         error_message = f"Invalid argument provided for {operation_description}: {e}"
    elif isinstance(e, google_exceptions.BadRequest):
        error_message = f"Bad request during {operation_description} (check arguments/query): {e}"
    # Add more specific GCP exception handling as needed

    logger.error(f"GCP Error during {operation_description}: {e}", exc_info=True)
    return format_error(error_message, data=details)
