import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import timedelta, datetime, timezone

from google.cloud import storage
from google.api_core import exceptions as google_exceptions
from mcp import types as mcp_types

try:
    from ..utils import (
        format_success, format_error, handle_gcp_error,
        McpToolReturnType, retry_on_gcp_transient_error
    )
except ImportError:
    logging.critical("Failed to import utils in gcs_tools_temp.py. Ensure PYTHONPATH is correct.")
    # Define dummy decorators/formatters if utils not found, to allow basic loading
    def retry_on_gcp_transient_error(func): return func
    def format_success(msg, data=None): return [mcp_types.TextContent(type="text", text=f'{{"status": "success", "message": "{msg}", "data": {data or {}}}}')]
    def format_error(msg, data=None): return [mcp_types.TextContent(type="text", text=f'{{"status": "error", "message": "{msg}", "data": {data or {}}}}')]
    def handle_gcp_error(e, desc): return [mcp_types.TextContent(type="text", text=f'{{"status": "error", "message": "GCP Error in {desc}: {e}"}}')]
    McpToolReturnType = List[mcp_types.Content]


logger = logging.getLogger("mcp_agent.gcp_tools.storage") # Target logger name

_storage_client: Optional[storage.Client] = None

def get_storage_client() -> storage.Client:
    """Initializes and returns a cached GCS client using Application Default Credentials."""
    global _storage_client
    if _storage_client is None:
        logger.info("Initializing Google Cloud Storage client.")
        try:
            _storage_client = storage.Client()
            logger.info("Google Cloud Storage client initialized successfully.")
        except Exception as e:
            logger.critical(f"Failed to initialize GCS client: {e}", exc_info=True)
            raise RuntimeError(f"GCS client initialization failed: {e}") from e
    return _storage_client

# --- Synchronous helpers with retry ---
@retry_on_gcp_transient_error
def _list_buckets_sync(client: storage.Client, project_id: Optional[str]) -> List[str]:
    logger.debug(f"Running GCS list buckets for project {project_id or 'default client project'}")
    buckets = client.list_buckets(project=project_id)
    return [bucket.name for bucket in buckets]

@retry_on_gcp_transient_error
def _list_blobs_sync(client: storage.Client, bucket_name: str, prefix: Optional[str], delimiter: Optional[str]) -> List[Dict[str, Any]]:
    logger.debug(f"Running GCS list blobs for bucket '{bucket_name}', prefix '{prefix}', delimiter '{delimiter}'")
    bucket = client.bucket(bucket_name)
    blobs_iterator = bucket.list_blobs(prefix=prefix, delimiter=delimiter)
    results = []
    for blob_item in blobs_iterator:
        results.append({
            "name": blob_item.name,
            "size": blob_item.size,
            "updated": blob_item.updated.isoformat() if blob_item.updated else None,
            "content_type": blob_item.content_type
        })
    # If delimiter is used, prefixes (virtual folders) are also in blobs_iterator.prefixes
    if delimiter and hasattr(blobs_iterator, 'prefixes') and blobs_iterator.prefixes:
        for p in blobs_iterator.prefixes:
            results.append({"name": p, "type": "prefix"}) # Indicate it's a prefix
    return results

@retry_on_gcp_transient_error
def _upload_string_sync(client: storage.Client, bucket_name: str, object_name: str, content: str, content_type: Optional[str]):
    logger.debug(f"Running GCS upload string to '{bucket_name}/{object_name}'")
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    blob.upload_from_string(content, content_type=content_type or 'text/plain')
    return {"name": blob.name, "bucket": blob.bucket.name, "size": blob.size, "content_type": blob.content_type}

@retry_on_gcp_transient_error
def _generate_signed_url_sync(
    client: storage.Client,
    bucket_name: str,
    object_name: str,
    method: str,
    expiration_delta: timedelta,
    content_type: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    version: str = "v4"
) -> str:
    logger.debug(f"Generating GCS {method} signed URL for '{bucket_name}/{object_name}', version '{version}'")
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)

    # Ensure expiration is timezone-aware for v4, though timedelta handles it.
    # The library now prefers timedelta directly for expiration.

    url = blob.generate_signed_url(
        version=version,
        expiration=expiration_delta,
        method=method,
        content_type=content_type,
        headers=headers
    )
    return url

# --- Async Tool Implementations ---

async def gcs_list_buckets(arguments: Dict[str, Any], conn_id: str, **kwargs) -> McpToolReturnType:
    project_id = arguments.get("project_id")
    if project_id is not None and not isinstance(project_id, str):
        return format_error("Invalid 'project_id', must be a string.")
    try:
        client = get_storage_client()
        bucket_names = await asyncio.to_thread(_list_buckets_sync, client, project_id)
        return format_success("Buckets listed successfully.", data={"buckets": bucket_names, "project_id": project_id or client.project})
    except Exception as e:
        return handle_gcp_error(e, f"listing GCS buckets for project '{project_id or 'default'}'")

async def gcs_list_objects(arguments: Dict[str, Any], conn_id: str, **kwargs) -> McpToolReturnType:
    bucket_name = arguments.get("bucket_name")
    prefix = arguments.get("prefix")
    delimiter = arguments.get("delimiter")

    if not bucket_name or not isinstance(bucket_name, str):
        return format_error("Missing or invalid 'bucket_name' argument.")
    if prefix is not None and not isinstance(prefix, str):
        return format_error("Invalid 'prefix' argument, must be a string.")
    if delimiter is not None and not isinstance(delimiter, str):
        return format_error("Invalid 'delimiter' argument, must be a string.")

    try:
        client = get_storage_client()
        objects = await asyncio.to_thread(_list_blobs_sync, client, bucket_name, prefix, delimiter)
        return format_success(f"Objects listed for bucket '{bucket_name}'.", data={"bucket_name": bucket_name, "objects": objects})
    except google_exceptions.NotFound:
        return format_error(f"Bucket '{bucket_name}' not found.")
    except Exception as e:
        return handle_gcp_error(e, f"listing objects in GCS bucket '{bucket_name}'")

async def gcs_get_read_signed_url(arguments: Dict[str, Any], conn_id: str, **kwargs) -> McpToolReturnType:
    bucket_name = arguments.get("bucket_name")
    object_name = arguments.get("object_name")
    expiration_minutes = arguments.get("expiration_minutes", 60) # Default to 60 minutes

    if not bucket_name or not isinstance(bucket_name, str):
        return format_error("Missing or invalid 'bucket_name'.")
    if not object_name or not isinstance(object_name, str):
        return format_error("Missing or invalid 'object_name'.")
    try:
        expiration_minutes = int(expiration_minutes)
        if expiration_minutes <= 0 or expiration_minutes > 7 * 24 * 60: # Max 7 days for v4
             raise ValueError("Expiration must be between 1 minute and 7 days (10080 minutes).")
    except ValueError:
        return format_error("Invalid 'expiration_minutes', must be a positive integer (max 10080).")

    try:
        client = get_storage_client()
        expiration_delta = timedelta(minutes=expiration_minutes)

        # For GET, content_type and headers are usually not needed for the URL itself
        # unless specific response headers are desired from GCS (response_disposition, etc.)
        # which can be passed via `response_disposition` or `response_type` to generate_signed_url.
        # For simplicity, we are not including them here unless a specific need arises.

        signed_url = await asyncio.to_thread(
            _generate_signed_url_sync,
            client, bucket_name, object_name, "GET", expiration_delta, version="v4"
        )
        return format_success("Read signed URL generated.", data={
            "bucket_name": bucket_name,
            "object_name": object_name,
            "signed_url": signed_url,
            "method": "GET",
            "expires_at": (datetime.now(timezone.utc) + expiration_delta).isoformat()
        })
    except google_exceptions.NotFound: # Bucket or blob might not exist, though URL can still be generated
        logger.warning(f"GCS Read Signed URL: Bucket '{bucket_name}' or object '{object_name}' may not exist, but URL generated.", exc_info=False)
        # Depending on strictness, one might error here or let the client discover the 404.
        # For now, let the URL be generated; the client will get a 404 if the object doesn't exist.
        # Re-raising to be caught by handle_gcp_error if that's the desired behavior for non-existence.
        # However, generate_signed_url itself doesn't check existence.
        # Let's assume the primary error source would be IAM for token creation.
        return format_error(f"Could not generate read signed URL. Ensure bucket '{bucket_name}' and object '{object_name}' exist if access fails, or check IAM permissions for the service account (needs Service Account Token Creator on itself).")

    except Exception as e:
        return handle_gcp_error(e, f"generating read signed URL for '{bucket_name}/{object_name}'")


async def gcs_get_write_signed_url(arguments: Dict[str, Any], conn_id: str, **kwargs) -> McpToolReturnType:
    bucket_name = arguments.get("bucket_name")
    object_name = arguments.get("object_name")
    expiration_minutes = arguments.get("expiration_minutes", 60) # Default to 60 minutes
    content_type = arguments.get("content_type") # Optional, e.g., 'application/octet-stream' or 'image/jpeg'
    custom_headers = arguments.get("headers") # Optional custom headers like 'x-goog-meta-*'

    if not bucket_name or not isinstance(bucket_name, str):
        return format_error("Missing or invalid 'bucket_name'.")
    if not object_name or not isinstance(object_name, str):
        return format_error("Missing or invalid 'object_name'.")
    if content_type is not None and not isinstance(content_type, str):
        return format_error("Invalid 'content_type', must be a string if provided.")
    if custom_headers is not None and not isinstance(custom_headers, dict):
        return format_error("Invalid 'headers', must be a dictionary if provided.")

    try:
        expiration_minutes = int(expiration_minutes)
        if expiration_minutes <= 0 or expiration_minutes > 7 * 24 * 60:
             raise ValueError("Expiration must be between 1 minute and 7 days (10080 minutes).")
    except ValueError:
        return format_error("Invalid 'expiration_minutes', must be a positive integer (max 10080).")

    try:
        client = get_storage_client()
        expiration_delta = timedelta(minutes=expiration_minutes)

        signed_url = await asyncio.to_thread(
            _generate_signed_url_sync,
            client, bucket_name, object_name, "PUT", expiration_delta,
            content_type=content_type, headers=custom_headers, version="v4"
        )
        return format_success("Write signed URL generated.", data={
            "bucket_name": bucket_name,
            "object_name": object_name,
            "signed_url": signed_url,
            "method": "PUT",
            "content_type_expected": content_type, # Client should use this Content-Type header
            "custom_headers_expected": custom_headers, # Client should include these headers
            "expires_at": (datetime.now(timezone.utc) + expiration_delta).isoformat()
        })
    except Exception as e: # Catch broad exceptions, including potential IAM issues for SA Token Creator
        return handle_gcp_error(e, f"generating write signed URL for '{bucket_name}/{object_name}'")

async def gcs_write_string_object(arguments: Dict[str, Any], conn_id: str, **kwargs) -> McpToolReturnType:
    bucket_name = arguments.get("bucket_name")
    object_name = arguments.get("object_name")
    content = arguments.get("content")
    content_type = arguments.get("content_type") # Optional

    if not bucket_name or not isinstance(bucket_name, str):
        return format_error("Missing or invalid 'bucket_name'.")
    if not object_name or not isinstance(object_name, str):
        return format_error("Missing or invalid 'object_name'.")
    if content is None or not isinstance(content, str): # Content must be string for this tool
        return format_error("Missing or invalid 'content', must be a string.")
    if content_type is not None and not isinstance(content_type, str):
        return format_error("Invalid 'content_type', must be a string if provided.")

    try:
        client = get_storage_client()
        upload_result = await asyncio.to_thread(
            _upload_string_sync, client, bucket_name, object_name, content, content_type
        )
        return format_success(f"String content written to '{bucket_name}/{object_name}'.", data=upload_result)
    except google_exceptions.NotFound:
        return format_error(f"Bucket '{bucket_name}' not found.")
    except Exception as e:
        return handle_gcp_error(e, f"writing string to GCS object '{bucket_name}/{object_name}'")
