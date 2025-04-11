# mcp_agent/gcp_tools/__init__.py
# Make tools easily importable
from .storage import (
    gcs_list_buckets,
    gcs_set_context_bucket,
    gcs_clear_context_bucket,
    gcs_list_objects,
    gcs_read_object,
    gcs_write_object,
)
from .bigquery import (
    bq_set_context_dataset,
    bq_clear_context_dataset,
    bq_list_datasets,
    bq_list_tables,
    bq_get_table_schema,
    bq_query,
)

# Define tool schemas for MCP advertisement
from mcp import types as mcp_types

# Schemas can be complex, defining them manually here for clarity
# In a real app, you might generate these from function signatures or dataclasses

GCS_TOOLS_SCHEMAS = [
    mcp_types.Tool(
        name="gcs_list_buckets",
        description="Lists accessible Google Cloud Storage buckets.",
        arguments={},
    ),
    mcp_types.Tool(
        name="gcs_set_context_bucket",
        description="Sets the default GCS bucket for subsequent commands in this session.",
        arguments={
            "bucket_name": mcp_types.ToolArgument(
                type="string", description="The name of the GCS bucket.", is_required=True
            )
        },
    ),
     mcp_types.Tool(
        name="gcs_clear_context_bucket",
        description="Clears the default GCS bucket context for this session.",
        arguments={},
    ),
    mcp_types.Tool(
        name="gcs_list_objects",
        description="Lists objects and common prefixes (directories) in a GCS bucket. Uses context bucket if 'bucket_name' is omitted. Supports pagination.",
        arguments={
            "bucket_name": mcp_types.ToolArgument(type="string", description="Specific bucket name (overrides context).", is_required=False),
            "prefix": mcp_types.ToolArgument(type="string", description="Filter results by this prefix (e.g., 'images/').", is_required=False),
            "page_token": mcp_types.ToolArgument(type="string", description="Token from a previous response to get the next page.", is_required=False),
            "max_results": mcp_types.ToolArgument(type="integer", description="Maximum items per page.", is_required=False, default_value=100),
        },
    ),
    mcp_types.Tool(
        name="gcs_read_object",
        description="Reads the content of an object in a GCS bucket. Uses context bucket if 'bucket_name' is omitted.",
        arguments={
            "object_path": mcp_types.ToolArgument(type="string", description="The full path to the object within the bucket.", is_required=True),
            "bucket_name": mcp_types.ToolArgument(type="string", description="Specific bucket name (overrides context).", is_required=False),
        },
    ),
     mcp_types.Tool(
        name="gcs_write_object",
        description="Writes string content to an object in a GCS bucket. Uses context bucket if 'bucket_name' is omitted. Overwrites if exists.",
        arguments={
            "object_path": mcp_types.ToolArgument(type="string", description="The full path for the object within the bucket.", is_required=True),
            "content": mcp_types.ToolArgument(type="string", description="The string content to write.", is_required=True),
            "bucket_name": mcp_types.ToolArgument(type="string", description="Specific bucket name (overrides context).", is_required=False),
        },
    ),
]

BQ_TOOLS_SCHEMAS = [
    mcp_types.Tool(
        name="bq_set_context_dataset",
        description="Sets the default BigQuery project and dataset for subsequent commands.",
        arguments={
            "project_id": mcp_types.ToolArgument(type="string", description="The Google Cloud project ID.", is_required=True),
            "dataset_id": mcp_types.ToolArgument(type="string", description="The BigQuery dataset ID.", is_required=True),
        },
    ),
     mcp_types.Tool(
        name="bq_clear_context_dataset",
        description="Clears the default BigQuery project/dataset context.",
        arguments={},
    ),
     mcp_types.Tool(
        name="bq_list_datasets",
        description="Lists accessible BigQuery datasets within a project.",
        arguments={
            "project_id": mcp_types.ToolArgument(type="string", description="Specific project ID (defaults to server's default project if omitted).", is_required=False),
        },
    ),
     mcp_types.Tool(
        name="bq_list_tables",
        description="Lists tables within a BigQuery dataset. Uses context if project/dataset IDs are omitted.",
        arguments={
             "project_id": mcp_types.ToolArgument(type="string", description="Specific project ID (overrides context).", is_required=False),
             "dataset_id": mcp_types.ToolArgument(type="string", description="Specific dataset ID (overrides context).", is_required=False),
        },
    ),
    mcp_types.Tool(
        name="bq_get_table_schema",
        description="Gets the schema of a BigQuery table. Uses context project/dataset if IDs are omitted.",
        arguments={
            "table_id": mcp_types.ToolArgument(type="string", description="Table ID (e.g., 'my_table' or 'dataset.my_table').", is_required=True),
            "project_id": mcp_types.ToolArgument(type="string", description="Specific project ID (overrides context).", is_required=False),
            "dataset_id": mcp_types.ToolArgument(type="string", description="Specific dataset ID (overrides context).", is_required=False),
        },
    ),
    mcp_types.Tool(
        name="bq_query",
        description="Executes a SQL query in BigQuery. Uses context project/dataset for unqualified table names.",
        arguments={
            "query": mcp_types.ToolArgument(type="string", description="The SQL query string.", is_required=True),
            "project_id": mcp_types.ToolArgument(type="string", description="Project ID to run the query in (overrides context default project).", is_required=False),
            "dataset_id": mcp_types.ToolArgument(type="string", description="Default dataset ID for unqualified table names (overrides context default dataset).", is_required=False),
            "max_results": mcp_types.ToolArgument(type="integer", description="Maximum rows to return in the first page.", is_required=False, default_value=1000),
            "page_token": mcp_types.ToolArgument(type="string", description="Page token from a previous query result to fetch the next page.", is_required=False),
        },
    ),
]

# Map tool names to functions
ALL_TOOLS_MAP = {
    "gcs_list_buckets": gcs_list_buckets,
    "gcs_set_context_bucket": gcs_set_context_bucket,
    "gcs_clear_context_bucket": gcs_clear_context_bucket,
    "gcs_list_objects": gcs_list_objects,
    "gcs_read_object": gcs_read_object,
    "gcs_write_object": gcs_write_object,
    "bq_set_context_dataset": bq_set_context_dataset,
    "bq_clear_context_dataset": bq_clear_context_dataset,
    "bq_list_datasets": bq_list_datasets,
    "bq_list_tables": bq_list_tables,
    "bq_get_table_schema": bq_get_table_schema,
    "bq_query": bq_query,
}
