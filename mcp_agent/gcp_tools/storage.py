# mcp_agent/gcp_tools/storage.py
import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from google.cloud import bigquery
from google.api_core import exceptions as google_exceptions, page_iterator
from mcp import types as mcp_types

from ..context import ConnectionContextManager
from ..utils import format_success, format_error, format_info, handle_gcp_error

logger = logging.getLogger(__name__)

# Cache the client
bq_client = None

def get_bq_client():
    global bq_client
    if bq_client is None:
        logger.info("Initializing Google Cloud BigQuery client...")
        try:
            # Relies on Application Default Credentials (ADC)
            bq_client = bigquery.Client()
            logger.info("Google Cloud BigQuery client initialized successfully.")
        except Exception as e:
             logger.error(f"Failed to initialize Google Cloud BigQuery client: {e}", exc_info=True)
             raise
    return bq_client

async def bq_set_context_dataset(
    arguments: Dict[str, Any], conn_id: str, context_manager: ConnectionContextManager
) -> List[mcp_types.TextContent]:
    project_id = arguments.get("project_id")
    dataset_id = arguments.get("dataset_id")
    if not project_id or not dataset_id:
        return format_error("Missing required arguments: 'project_id' and 'dataset_id'.")

    # Validate dataset existence/access
    try:
        client = get_bq_client()
        dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
        # Run blocking call in thread
        await asyncio.to_thread(client.get_dataset, dataset_ref) # Raises NotFound/Forbidden on failure

        await context_manager.set_bq_context(conn_id, project_id, dataset_id)
        return format_success(f"BQ context set to dataset '{project_id}:{dataset_id}'.")
    except google_exceptions.NotFound:
         logger.warning(f"Dataset '{project_id}:{dataset_id}' not found during context setting.")
         return format_error(f"Dataset '{project_id}:{dataset_id}' not found. Cannot set context.")
    except google_exceptions.Forbidden:
         logger.warning(f"Permission denied accessing dataset '{project_id}:{dataset_id}' for context setting.")
         return format_error(f"Permission denied for dataset '{project_id}:{dataset_id}'. Cannot set context.")
    except Exception as e:
        return handle_gcp_error(e, f"setting BQ context to dataset '{project_id}:{dataset_id}'")

async def bq_clear_context_dataset(
    arguments: Dict[str, Any], conn_id: str, context_manager: ConnectionContextManager
) -> List[mcp_types.TextContent]:
     await context_manager.clear_bq_context(conn_id)
     return format_success("BigQuery dataset context cleared.")


async def bq_list_datasets(
    arguments: Dict[str, Any], conn_id: str, context_manager: ConnectionContextManager
) -> List[mcp_types.TextContent]:
    project_id = arguments.get("project_id") # Can be None
    try:
        client = get_bq_client()
        # Run blocking iterator consumption in thread
        datasets_iterator = await asyncio.to_thread(client.list_datasets, project=project_id)
        dataset_list = [ds.dataset_id for ds in datasets_iterator]
        used_project = project_id or client.project # Get the project ID actually used
        return format_success("Datasets listed successfully.", data={"project_id": used_project, "datasets": dataset_list})
    except Exception as e:
        return handle_gcp_error(e, f"listing BQ datasets for project '{project_id or 'default'}'")

async def _get_bq_context_or_error(
    arguments: Dict[str, Any], conn_id: str, context_manager: ConnectionContextManager
) -> Tuple[Optional[str], Optional[str], Optional[List[mcp_types.TextContent]]]:
    """Helper to get project/dataset from args or context."""
    # Prioritize arguments
    project_id = arguments.get("project_id")
    dataset_id = arguments.get("dataset_id")

    # If both args provided, use them
    if project_id and dataset_id:
        return project_id, dataset_id, None

    # Try context if args are incomplete
    context_ids = await context_manager.get_bq_context(conn_id)
    ctx_project, ctx_dataset = context_ids if context_ids else (None, None)

    # Resolve final IDs: arg > context
    final_project_id = project_id if project_id else ctx_project
    final_dataset_id = dataset_id if dataset_id else ctx_dataset

    # Check if resolution was successful
    if final_project_id and final_dataset_id:
        return final_project_id, final_dataset_id, None
    else:
        # Construct a helpful error message
        missing = []
        if not final_project_id: missing.append("project_id")
        if not final_dataset_id: missing.append("dataset_id")
        error_msg = f"Cannot perform operation: Missing { ' and '.join(missing) }."
        if not context_ids:
            error_msg += " No BQ context is set."
        else:
             error_msg += f" Provide the missing ID(s) or ensure BQ context ('{ctx_project}:{ctx_dataset}') is correct."
        return None, None, format_error(error_msg)


async def bq_list_tables(
    arguments: Dict[str, Any], conn_id: str, context_manager: ConnectionContextManager
) -> List[mcp_types.TextContent]:
    project_id, dataset_id, error_response = await _get_bq_context_or_error(arguments, conn_id, context_manager)
    if error_response:
        return error_response

    try:
        client = get_bq_client()
        dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
        # Run blocking iterator consumption in thread
        tables_iterator = await asyncio.to_thread(client.list_tables, dataset_ref)
        table_list = [table.table_id for table in tables_iterator]
        return format_success(
            "Tables listed successfully.",
             data={"project_id": project_id, "dataset_id": dataset_id, "tables": table_list}
        )
    except Exception as e:
        return handle_gcp_error(e, f"listing BQ tables for dataset '{project_id}:{dataset_id}'")

async def bq_get_table_schema(
    arguments: Dict[str, Any], conn_id: str, context_manager: ConnectionContextManager
) -> List[mcp_types.TextContent]:
    table_id_arg = arguments.get("table_id")
    if not table_id_arg:
         return format_error("Missing required argument: 'table_id'.")

    project_id_arg = arguments.get("project_id")
    dataset_id_arg = arguments.get("dataset_id")

    # Resolve project/dataset: Args override context
    target_project_id = project_id_arg
    target_dataset_id = dataset_id_arg
    target_table_id = table_id_arg

    # Parse fully qualified name if provided
    if '.' in table_id_arg:
        parts = table_id_arg.split('.')
        num_parts = len(parts)
        # If project provided in arg, it overrides anything in table_id_arg
        # If dataset provided in arg, it overrides anything in table_id_arg
        if num_parts == 3:
             target_project_id = project_id_arg or parts[0]
             target_dataset_id = dataset_id_arg or parts[1]
             target_table_id = parts[2]
        elif num_parts == 2:
            target_dataset_id = dataset_id_arg or parts[0]
            target_table_id = parts[1]
            # Project still needs resolution if not in args
            if not target_project_id:
                 context_ids = await context_manager.get_bq_context(conn_id)
                 target_project_id = context_ids[0] if context_ids else None
        else:
            return format_error("Invalid table_id format. Use 'table', 'dataset.table', or 'project.dataset.table'.")
    else:
         # Simple table name, requires context or args for project/dataset
         if not target_project_id or not target_dataset_id:
              context_ids = await context_manager.get_bq_context(conn_id)
              if context_ids:
                   ctx_project, ctx_dataset = context_ids
                   if not target_project_id: target_project_id = ctx_project
                   if not target_dataset_id: target_dataset_id = ctx_dataset
              # If context didn't resolve, check if args were enough
              # (This case should be rare if initial arg checks are done)
              if not target_project_id or not target_dataset_id:
                   return format_error("Cannot resolve table: Missing project/dataset ID and no BQ context set.")


    if not target_project_id or not target_dataset_id or not target_table_id:
         # This check should ideally be covered by the logic above, but acts as a failsafe
         return format_error(f"Could not determine full table reference for '{table_id_arg}'. Resolved: P={target_project_id}, D={target_dataset_id}, T={target_table_id}")

    try:
        client = get_bq_client()
        table_ref_str = f"{target_project_id}.{target_dataset_id}.{target_table_id}"
        logger.info(f"Getting schema for resolved table reference: {table_ref_str}")
        table_ref = bigquery.TableReference.from_string(table_ref_str)
        # Run blocking call in thread
        table = await asyncio.to_thread(client.get_table, table_ref)

        schema_list = [{"name": field.name, "type": field.field_type, "mode": field.mode} for field in table.schema]
        return format_success(
            "Table schema retrieved successfully.",
            data={
                 "project_id": table.project,
                 "dataset_id": table.dataset_id,
                 "table_id": table.table_id,
                 "schema": schema_list,
            }
        )
    except google_exceptions.NotFound:
        logger.warning(f"Table '{table_ref_str}' not found.")
        return format_error(f"Table '{table_ref_str}' not found.")
    except Exception as e:
         return handle_gcp_error(e, f"getting schema for table '{table_ref_str}'")


async def bq_query(
    arguments: Dict[str, Any], conn_id: str, context_manager: ConnectionContextManager
) -> List[mcp_types.TextContent]:
    query_str = arguments.get("query")
    if not query_str:
        return format_error("Missing required argument: 'query'.")

    project_id_arg = arguments.get("project_id")
    dataset_id_arg = arguments.get("dataset_id")
    max_results = arguments.get("max_results", 1000) # Max results for the *current page*
    page_token = arguments.get("page_token")

    # Determine default project/dataset for the query job config
    # Allow overriding with args, fallback to context
    default_project, default_dataset, _ = await _get_bq_context_or_error(arguments, conn_id, context_manager)
    # Note: _get_bq_context_or_error might return None even if context exists, if only one arg was provided.
    # We prioritize args for job config if provided.

    target_project = project_id_arg # Project to run the job in, might be None
    job_default_dataset_ref = None
    if default_project and default_dataset:
         job_default_dataset_ref = bigquery.DatasetReference(default_project, default_dataset)


    try:
        client = get_bq_client()
        # If target project wasn't specified via arg, use client's default.
        if not target_project:
             target_project = client.project
             logger.info(f"No project specified for query job, using client default project: {target_project}")

        job_config = bigquery.QueryJobConfig(use_legacy_sql=False) # Default to Standard SQL
        if job_default_dataset_ref: # Set default dataset for unqualified tables
            job_config.default_dataset = job_default_dataset_ref

        # --- WARNING ---
        # This submits the query and *blocks* until results are available using query_job.result().
        # This is NOT suitable for long-running queries (> ~30-60 seconds depending on client timeouts).
        # Production systems need an async job handling pattern:
        # 1. client.query() -> get job_id
        # 2. Return job_id to client
        # 3. Client uses separate tool `bq_get_query_results(job_id, page_token)`
        # 4. `bq_get_query_results` calls `client.get_job()` then `client.list_rows()`
        # --- END WARNING ---

        logger.info(f"Running BQ Query in Project '{target_project}' (Default Dataset: '{job_config.default_dataset or 'None'}'): {query_str[:100]}...")
        # Initiate query (non-blocking call, but the job runs on BQ)
        query_job = client.query(query_str, job_config=job_config, project=target_project)
        logger.info(f"BQ Job initiated: {query_job.job_id}")

        # Fetch results (blocking call) - run in thread
        logger.debug(f"Fetching results for job {query_job.job_id} with page_token: {page_token}, max_results: {max_results}")
        results_page = await asyncio.to_thread(
             query_job.result, # This blocks until query finishes
             page_token=page_token,
             max_results=max_results
        )
        logger.debug(f"Results fetched for job {query_job.job_id}. Rows on page: {len(results_page)}, Next token: {results_page.next_page_token}")


        # Convert results to JSON-serializable format
        schema_list = [{"name": field.name, "type": field.field_type} for field in results_page.schema]
        # Handle various data types that might not be directly JSON serializable
        def serialize_row(row):
            row_dict = {}
            for key, value in row.items():
                 if isinstance(value, (bytes,)): # Handle bytes
                     try:
                          row_dict[key] = value.decode('utf-8') # Assume UTF-8
                     except UnicodeDecodeError:
                          row_dict[key] = f"<bytes:{len(value)}>" # Placeholder
                 # Add handling for datetime, date, time, numeric, etc. if needed
                 # For now, rely on json.dumps default=str later
                 else:
                     row_dict[key] = value
            return row_dict

        rows_list = [serialize_row(row) for row in results_page]

        return format_success(
            "Query executed successfully.",
            data={
                "job_id": query_job.job_id,
                "total_rows": results_page.total_rows, # Total rows for the *entire* query result
                "schema": schema_list,
                "rows": rows_list, # Rows for the *current page*
                "next_page_token": results_page.next_page_token, # Token for the *next page of results*
            },
        )
    except google_exceptions.BadRequest as e:
         # Likely a syntax error or invalid query structure
         logger.warning(f"Query failed (BadRequest): {e}")
         return format_error(f"Query failed (likely syntax or semantic error): {e}", data={"details": str(e)})
    except google_exceptions.Forbidden as e:
         logger.warning(f"Query failed (Forbidden): {e}")
         return format_error(f"Permission denied for query execution or accessing tables: {e}", data={"details": str(e)})
    except Exception as e:
        return handle_gcp_error(e, f"executing BigQuery query")
