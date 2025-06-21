# mcp_agent/gcp_tools/__init__.py
# This file defines the available GCP tools for the MCP agent.

import logging
from typing import Dict, Callable, Awaitable, List
from mcp import types as mcp_types

logger = logging.getLogger("mcp_agent.gcp_tools")

# Import tool functions from their respective modules
# Note: These imports assume the functions are defined in these files.
# If a function isn't found, it means it hasn't been implemented or is misnamed.
try:
    from .storage import (
        gcs_list_buckets,
        gcs_list_objects,
        gcs_get_read_signed_url,
        gcs_get_write_signed_url,
        gcs_write_string_object,
        # get_storage_client # Typically not a tool itself, but a helper
    )
    logger.debug("Successfully imported GCS tools from .storage")
except ImportError as e:
    logger.error(f"Error importing GCS tools from .storage: {e}. Some GCS tools may not be available.", exc_info=True)
    # Define placeholders if import fails to prevent server from crashing on ALL_TOOLS_MAP access
    def _gcs_placeholder(*args, **kwargs): raise NotImplementedError("GCS tool not loaded due to import error")
    gcs_list_buckets = gcs_list_objects = gcs_get_read_signed_url = _gcs_placeholder
    gcs_get_write_signed_url = gcs_write_string_object = _gcs_placeholder


try:
    from .bigquery import (
        bq_list_datasets,
        bq_list_tables,
        bq_get_table_schema,
        bq_submit_query,
        bq_get_job_status,
        bq_get_query_results,
        # get_bq_client # Typically not a tool itself
    )
    logger.debug("Successfully imported BigQuery tools from .bigquery")
except ImportError as e:
    logger.error(f"Error importing BQ tools from .bigquery: {e}. Some BQ tools may not be available.", exc_info=True)
    def _bq_placeholder(*args, **kwargs): raise NotImplementedError("BQ tool not loaded due to import error")
    bq_list_datasets = bq_list_tables = bq_get_table_schema = _bq_placeholder
    bq_submit_query = bq_get_job_status = bq_get_query_results = _bq_placeholder


# ALL_TOOLS_MAP: Maps tool names (as called by MCP client) to their async function implementations.
# Each function is expected to take `arguments: Dict[str, Any], conn_id: str, **kwargs`
# and return `McpToolReturnType` (which is `List[mcp_types.Content]`).
# The `bq_job_store` will be passed in kwargs by the dispatcher if available.
ALL_TOOLS_MAP: Dict[str, Callable[..., Awaitable[List[mcp_types.Content]]]] = {
    # GCS Tools
    "gcs_list_buckets": gcs_list_buckets,
    "gcs_list_objects": gcs_list_objects,
    "gcs_get_read_signed_url": gcs_get_read_signed_url,
    "gcs_get_write_signed_url": gcs_get_write_signed_url,
    "gcs_write_string_object": gcs_write_string_object,

    # BigQuery Tools
    "bq_list_datasets": bq_list_datasets,
    "bq_list_tables": bq_list_tables,
    "bq_get_table_schema": bq_get_table_schema,
    "bq_submit_query": bq_submit_query,
    "bq_get_job_status": bq_get_job_status,
    "bq_get_query_results": bq_get_query_results,
}

logger.info(f"ALL_TOOLS_MAP initialized with {len(ALL_TOOLS_MAP)} tools: {list(ALL_TOOLS_MAP.keys())}")

# TODO: Define MCP Tool Schemas for advertisement (Priority 4 - Documentation)
# These schemas describe the tools, their arguments, and descriptions for MCP clients.
# Example structure:
# from mcp import types as mcp_types
# TOOL_SCHEMAS: List[mcp_types.Tool] = [
#     mcp_types.Tool(
#         name="gcs_list_buckets",
#         description="Lists accessible Google Cloud Storage buckets.",
#         arguments={
#             "project_id": mcp_types.ToolArgument(type="string", description="Optional GCP project ID.", is_required=False)
#         }
#     ),
#     # ... other tool schemas ...
# ]
# For now, this part is deferred. The server will function using ALL_TOOLS_MAP for dispatch.
# Client-side tool discovery and argument validation will be limited until schemas are provided.

# Ensure base.py is not directly exporting tools unless intended.
# It might contain base classes or shared utilities for tools.
from . import base
# If base.py has tool definitions, they should be explicitly imported and added to map.
# For now, assuming tools are in storage.py and bigquery.py.

# Clean up namespace if placeholders were defined due to import errors,
# though a better approach is to let the server fail on startup if core tools can't load.
# This cleanup is more for robustness if some non-critical tools failed to import.
_placeholders_to_remove = []
for tool_name, func in ALL_TOOLS_MAP.items():
    if hasattr(func, '__name__') and func.__name__ in ["_gcs_placeholder", "_bq_placeholder"]:
        _placeholders_to_remove.append(tool_name)

if _placeholders_to_remove:
    logger.warning(f"Removing placeholder tools due to import errors: {_placeholders_to_remove}")
    for tool_name in _placeholders_to_remove:
        del ALL_TOOLS_MAP[tool_name]

logger.info(f"Final ALL_TOOLS_MAP contains {len(ALL_TOOLS_MAP)} actively loaded tools.")
