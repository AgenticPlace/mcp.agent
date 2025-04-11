import json
import logging
import base64
from typing import Any, Dict, List, Optional, Union, Sequence

from google.api_core import exceptions as google_exceptions
from mcp import types as mcp_types
from google.cloud import secretmanager
# Import tenacity for retries
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type
)


logger = logging.getLogger("mcp_agent.utils") # Use specific logger

# Define a type alias for the common return type of tool functions
McpToolReturnType = List[mcp_types.Content]

# --- Retry Configuration ---
# Define exceptions that are generally safe to retry
RETRYABLE_GCP_EXCEPTIONS = (
    google_exceptions.ServerError,
    google_exceptions.ServiceUnavailable,
    google_exceptions.TooManyRequests,
    google_exceptions.DeadlineExceeded,
)

# Configure the retry decorator
# Stop after a few attempts use exponential backoff with jitter
retry_on_gcp_transient_error = retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=2), # Wait with jitter max few seconds
    retry=retry_if_exception_type(RETRYABLE_GCP_EXCEPTIONS),
    before_sleep=lambda retry_state: logger.warning(
        f"Retrying GCP operation exception {retry_state.outcome.exception()} attempt {retry_state.attempt_number} wait {retry_state.next_action.sleep:.2f}s",
        extra={ # Add context for structured logging
            'gcp_retry_attempt': retry_state.attempt_number,
            'gcp_retry_exception_type': type(retry_state.outcome.exception()).__name__,
            'gcp_retry_wait': round(retry_state.next_action.sleep, 2)
        }
    )
)
# --- End Retry Configuration ---


# Cache the Secret Manager client
_secret_manager_client: Optional[secretmanager.SecretManagerServiceClient] = None

def get_secret_manager_client() -> secretmanager.SecretManagerServiceClient:
    """Initializes returns cached Secret Manager client uses ADC"""
    global _secret_manager_client
    if _secret_manager_client is None:
        logger.info("Initializing Google Cloud Secret Manager client")
        try:
            _secret_manager_client = secretmanager.SecretManagerServiceClient()
            logger.info("Secret Manager client initialized successfully")
        except Exception as e:
            logger.critical(f"Failed to initialize Secret Manager client {e}", exc_info=True)
            raise RuntimeError(f"Secret Manager client initialization failed {e}") from e
    return _secret_manager_client

# Apply retry decorator to the function making the GCP call
@retry_on_gcp_transient_error
def _access_secret_version_sync(client: secretmanager.SecretManagerServiceClient, name: str) -> str:
    """Synchronous helper fetch secret wrapped with retry"""
    logger.debug(f"Accessing secret version sync {name}")
    request = secretmanager.AccessSecretVersionRequest(name=name)
    response = client.access_secret_version(request=request)
    # Secret payload is bytes decode assuming UTF8
    return response.payload.data.decode("UTF-8")

def fetch_secret(secret_version_name: str) -> Optional[str]:
    """
    Fetches secret payload from Secret Manager with retries

    Args secret version name full resource name

    Returns decoded secret string or None if fails permanently
    """
    if not secret_version_name or not isinstance(secret_version_name, str):
        logger.error("Invalid secret version name provided for fetching")
        return None

    try:
        client = get_secret_manager_client()
        logger.info(f"Attempting to access secret version {secret_version_name}")
        # Call retry wrapped synchronous function directly
        secret_payload = _access_secret_version_sync(client, name=secret_version_name)
        logger.info(f"Successfully accessed secret version {secret_version_name}")
        return secret_payload
    # Specific non retryable errors handled here
    except google_exceptions.NotFound:
        logger.error(f"Secret version not found {secret_version_name}")
        return None
    except google_exceptions.PermissionDenied:
        logger.error(f"Permission denied accessing secret version {secret_version_name} Ensure role", exc_info=True)
        return None
    # Catch errors after tenacity retries have failed
    except Exception as e:
        logger.error(f"Failed access secret version {secret_version_name} after retries {e}", exc_info=True)
        return None


def format_response( status: str, message: str, data: Optional[Dict[str, Any]] = None) -> McpToolReturnType:
    """Formats standard JSON response within single MCP TextContent object"""
    payload: Dict[str, Any] = {"status": status, "message": message}
    if data is not None: payload["data"] = data
    try: json_string = json.dumps(payload, default=str) # Use default str for non serializable types
    except TypeError as e:
        logger.error(f"JSON serialization error {e} payload {payload}", exc_info=True)
        payload = {"status": "error", "message": f"Internal server error serialization {e}"}
        json_string = json.dumps(payload)
    return [mcp_types.TextContent(type="text", text=json_string)]

# format chunked response remains but is unused by GCS now
def format_chunked_response( status: str, message: str, data: Optional[Dict[str, Any]] = None, chunks: Optional[Sequence[str]] = None ) -> McpToolReturnType:
    """Formats response possibly multiple TextContent chunks EXPERIMENTAL"""
    responses: McpToolReturnType = []
    base_payload: Dict[str, Any] = {"status": status, "message": message}
    if data is not None: base_payload["data"] = data
    if not chunks:
        logger.debug("Formatting single response no chunks")
        responses.append(mcp_types.TextContent(type="text", text=json.dumps(base_payload, default=str)))
    else:
        logger.debug(f"Formatting chunked response {len(chunks)} chunks")
        first_payload = base_payload.copy(); first_payload["chunking"] = {"total_chunks": len(chunks)}
        for i, chunk_content in enumerate(chunks):
            current_payload = first_payload if i == 0 else base_payload.copy(); current_payload["chunk_info"] = {"index": i}; current_payload["content_chunk"] = chunk_content
            try: json_string = json.dumps(current_payload, default=str)
            except TypeError as e:
                logger.error(f"JSON serialization error chunk {i} {e}", exc_info=True); json_string = json.dumps({"status": "error", "message": f"Error serializing chunk {i} {e}", "chunk_info": {"index": i}})
            responses.append(mcp_types.TextContent(type="text", text=json_string))
    return responses

def format_success( message: str, data: Optional[Dict[str, Any]] = None ) -> McpToolReturnType:
    """Helper for successful single responses"""
    return format_response("success", message, data)

def format_error( message: str, data: Optional[Dict[str, Any]] = None ) -> McpToolReturnType:
    """Helper for error single responses"""
    logger.warning(f"Operation error {message}" + (f" data {data}" if data else ""))
    return format_response("error", message, data)

def format_info( message: str, data: Optional[Dict[str, Any]] = None ) -> McpToolReturnType:
    """Helper for informational single responses"""
    return format_response("info", message, data)

def handle_gcp_error( e: Exception, operation_description: str) -> McpToolReturnType:
    """Handles common GCP exceptions formats standard error response"""
    error_message = f"Unexpected error during {operation_description} {type(e).__name__} {e}"
    details = {"exception_type": type(e).__name__, "exception_details": str(e)}
    # Map common GCP exceptions clearer messages
    if isinstance(e, google_exceptions.NotFound): error_message = f"Resource not found {operation_description} {e}"
    elif isinstance(e, google_exceptions.Forbidden): error_message = f"Permission denied {operation_description} Check credentials {e}"
    elif isinstance(e, google_exceptions.InvalidArgument): error_message = f"Invalid argument {operation_description} {e}"
    elif isinstance(e, google_exceptions.BadRequest): error_message = f"Bad request {operation_description} check args {e}"
    elif isinstance(e, google_exceptions.FailedPrecondition): error_message = f"Precondition failed {operation_description} {e}"
    elif isinstance(e, google_exceptions.AlreadyExists): error_message = f"Resource already exists {operation_description} {e}"
    logger.error(f"GCP Error {operation_description} {type(e).__name__} {e}", exc_info=True)
    return format_error(error_message, data=details)
