"""
Defines MCP tool schemas maps tool names implementation functions
for GCS BQ version 1 0 0 Stateless Context mcp_agent/jobstore.py
"""
# Import implementation functions
from .storage import (
    gcs_list_buckets,
    # Context tools removed
    gcs_list_objects,
    gcs_get_read_signed_url,
    gcs_get_write_signed_url,
    gcs_write_string_object,
)
from .bigquery import (
    # Context tools removed
    bq_list_datasets,
    bq_list_tables,
    bq_get_table_schema,
    bq_submit_query,
    bq_get_job_status,
    bq_get_query_results,
)

from mcp import types as mcp_types
from typing import Dict, Callable, Awaitable, Any, List
from ..utils import McpToolReturnType
GcpToolFunction = Callable[[Dict[str, Any], str, Any], Awaitable[McpToolReturnType]] # Type alias

# --- GCS Schemas Context args MANDATORY where applicable ---
GCS_TOOLS_SCHEMAS: List[mcp_types.Tool] = [
    mcp_types.Tool( name="gcs_list_buckets", description="Lists accessible GCS buckets", arguments={}),
    mcp_types.Tool(
        name="gcs_list_objects", description="Lists objects directories GCS bucket Supports pagination",
        arguments={
            "bucket_name": mcp_types.ToolArgument(type="string", description="Bucket name", is_required=True), # Required
            "prefix": mcp_types.ToolArgument(type="string", description="Filter by prefix", is_required=False),
            "page_token": mcp_types.ToolArgument(type="string", description="Token next page", is_required=False),
            "max_results": mcp_types.ToolArgument(type="integer", description="Max items page", is_required=False, default_value=100),
        }
    ),
    mcp_types.Tool(
        name="gcs_get_read_signed_url", description="Generates short lived URL read GCS object via HTTP GET",
        arguments={
            "bucket_name": mcp_types.ToolArgument(type="string", description="Bucket name", is_required=True), # Required
            "object_path": mcp_types.ToolArgument(type="string", description="Full path object", is_required=True),
            "expires_in_seconds": mcp_types.ToolArgument(type="integer", description="URL validity seconds", is_required=False, default_value=300),
        }
    ),
    mcp_types.Tool(
        name="gcs_get_write_signed_url", description="Generates short lived URL write GCS object via HTTP PUT",
        arguments={
            "bucket_name": mcp_types.ToolArgument(type="string", description="Bucket name", is_required=True), # Required
            "object_path": mcp_types.ToolArgument(type="string", description="Full path object write", is_required=True),
            "content_type": mcp_types.ToolArgument(type="string", description="Expected MIME type upload", is_required=False),
            "expires_in_seconds": mcp_types.ToolArgument(type="integer", description="URL validity seconds", is_required=False, default_value=300),
        }
    ),
    mcp_types.Tool(
        name="gcs_write_string_object", description="Writes small string content directly GCS Not large files",
        arguments={
            "bucket_name": mcp_types.ToolArgument(type="string", description="Bucket name", is_required=True), # Required
            "object_path": mcp_types.ToolArgument(type="string", description="Full path object", is_required=True),
            "content": mcp_types.ToolArgument(type="string", description="String content write", is_required=True),
        }
    ),
]

# --- BQ Schemas Context args MANDATORY where applicable ---
BQ_TOOLS_SCHEMAS: List[mcp_types.Tool] = [
    mcp_types.Tool( name="bq_list_datasets", description="Lists BQ datasets", arguments={ "project_id": mcp_types.ToolArgument(type="string", description="Project ID uses client default if omitted", is_required=False) } ),
    mcp_types.Tool( name="bq_list_tables", description="Lists tables BQ dataset", arguments={ "project_id": mcp_types.ToolArgument(type="string", description="Project ID", is_required=True), "dataset_id": mcp_types.ToolArgument(type="string", description="Dataset ID", is_required=True) } ),
    mcp_types.Tool( name="bq_get_table_schema", description="Gets schema BQ table", arguments={ "project_id": mcp_types.ToolArgument(type="string", description="Project ID", is_required=True), "dataset_id": mcp_types.ToolArgument(type="string", description="Dataset ID", is_required=True), "table_id": mcp_types.ToolArgument(type="string", description="Table ID", is_required=True) } ),
    mcp_types.Tool( name="bq_submit_query", description="Submits BQ query asynchronously", arguments={ "query": mcp_types.ToolArgument(type="string", description="SQL query", is_required=True), "project_id": mcp_types.ToolArgument(type="string", description="Project ID run query uses client default omitted", is_required=False), "default_dataset_project_id": mcp_types.ToolArgument(type="string", description="Default Project ID unqualified tables", is_required=False), "default_dataset_id": mcp_types.ToolArgument(type="string", description="Default Dataset ID unqualified tables", is_required=False) } ),
    mcp_types.Tool( name="bq_get_job_status", description="Checks status BQ job", arguments={ "job_id": mcp_types.ToolArgument(type="string", is_required=True), "location": mcp_types.ToolArgument(type="string", is_required=False) } ),
    mcp_types.Tool( name="bq_get_query_results", description="Fetches results page completed BQ job", arguments={ "job_id": mcp_types.ToolArgument(type="string", is_required=True), "page_token": mcp_types.ToolArgument(type="string", is_required=True), "max_results": mcp_types.ToolArgument(type="integer", default_value=1000, is_required=False), "location": mcp_types.ToolArgument(type="string", is_required=False) } ),
]

# --- Map tool names functions Removed context tools ---
ALL_TOOLS_MAP: Dict[str, GcpToolFunction] = {
    # GCS
    "gcs_list_buckets": gcs_list_buckets,
    "gcs_list_objects": gcs_list_objects,
    "gcs_get_read_signed_url": gcs_get_read_signed_url,
    "gcs_get_write_signed_url": gcs_get_write_signed_url,
    "gcs_write_string_object": gcs_write_string_object,
    # BQ
    "bq_list_datasets": bq_list_datasets,
    "bq_list_tables": bq_list_tables,
    "bq_get_table_schema": bq_get_table_schema,
    "bq_submit_query": bq_submit_query,
    "bq_get_job_status": bq_get_job_status,
    "bq_get_query_results": bq_get_query_results,
}
