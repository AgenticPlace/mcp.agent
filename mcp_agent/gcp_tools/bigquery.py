import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple, Sequence

from google.cloud import bigquery
from google.api_core import exceptions as google_exceptions, page_iterator
from mcp import types as mcp_types

# REMOVED: ConnectionContextManager import
from ..job_store import FirestoreBqJobStore # Import Firestore store
from ..utils import format_success, format_error, format_info, handle_gcp_error, McpToolReturnType
# Import retry decorator
from ..utils import retry_on_gcp_transient_error

logger = logging.getLogger("mcp_agent.gcp_tools.bigquery")

_bq_client: Optional[bigquery.Client] = None # Keep client cache

def get_bq_client() -> bigquery.Client:
    """Initializes and returns a cached BigQuery client using Application Default Credentials."""
    global _bq_client
    if _bq_client is None:
        logger.info("Initializing Google Cloud BigQuery client.")
        try:
            _bq_client = bigquery.Client()
            logger.info("Google Cloud BigQuery client initialized successfully.")
        except Exception as e:
            logger.critical(f"Failed to initialize BigQuery client: {e}", exc_info=True)
            raise RuntimeError(f"BigQuery client initialization failed: {e}") from e
    return _bq_client

# --- Apply Retry Decorator Sync Helpers ---
@retry_on_gcp_transient_error
def _get_dataset_sync(client: bigquery.Client, dataset_ref: bigquery.DatasetReference):
    logger.debug(f"Running client get dataset thread {dataset_ref} retry")
    client.get_dataset(dataset_ref)

@retry_on_gcp_transient_error
def _list_datasets_sync(client: bigquery.Client, project_id: Optional[str]):
    logger.debug(f"Running client list datasets thread project {project_id or 'default'} retry")
    return [ds.dataset_id for ds in client.list_datasets(project=project_id)], (project_id or client.project)

@retry_on_gcp_transient_error
def _list_tables_sync(client: bigquery.Client, dataset_ref: bigquery.DatasetReference):
    logger.debug(f"Running client list tables thread {dataset_ref} retry")
    return [table.table_id for table in client.list_tables(dataset_ref)]

@retry_on_gcp_transient_error
def _get_table_sync(client: bigquery.Client, table_ref: bigquery.TableReference):
    logger.debug(f"Running client get table thread {table_ref} retry")
    return client.get_table(table_ref)

@retry_on_gcp_transient_error
def _submit_job_sync(client: bigquery.Client, query_str: str, job_config: bigquery.QueryJobConfig, project: str):
    logger.debug(f"Running client query thread project {project} retry")
    return client.query(query=query_str, job_config=job_config, project=project)

@retry_on_gcp_transient_error
def _get_job_sync(client: bigquery.Client, job_id: str, location: Optional[str]):
    logger.debug(f"Running client get job thread {job_id} retry")
    return client.get_job(job_id, location=location)

@retry_on_gcp_transient_error
def _list_rows_sync(client: bigquery.Client, job_id: str, location: Optional[str], page_token: Optional[str], max_results: int):
     logger.debug(f"Running client list rows thread page job {job_id} retry")
     rows_iterator = client.list_rows(job_id, location=location, page_token=page_token, max_results=max_results)
     page_rows = list(rows_iterator) # Consume page
     return rows_iterator.schema, page_rows, rows_iterator.next_page_token, rows_iterator.total_rows

# --- Tool Implementations Require explicit args ---

async def bq_list_datasets( arguments: Dict[str, Any], conn_id: str, bq_job_store: FirestoreBqJobStore, **kwargs ) -> McpToolReturnType:
    """Lists accessible BQ datasets"""
    project_id = arguments.get("project_id"); # ... type validation ...
    if project_id is not None and not isinstance(project_id, str): return format_error("Invalid project id must be string")
    try:
        client = get_bq_client()
        dataset_list, used_project = await asyncio.to_thread(_list_datasets_sync, client, project_id)
        return format_success("Datasets listed", data={"project_id": used_project, "datasets": dataset_list})
    except Exception as e: return handle_gcp_error(e, f"listing BQ datasets project {project_id or 'default'}")

async def bq_list_tables( arguments: Dict[str, Any], conn_id: str, bq_job_store: FirestoreBqJobStore, **kwargs ) -> McpToolReturnType:
    """Lists tables within required BQ dataset"""
    project_id = arguments.get("project_id"); dataset_id = arguments.get("dataset_id")
    if not project_id or not isinstance(project_id, str): return format_error("Missing invalid project id")
    if not dataset_id or not isinstance(dataset_id, str): return format_error("Missing invalid dataset id")
    try:
        client = get_bq_client(); dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
        table_list = await asyncio.to_thread(_list_tables_sync, client, dataset_ref)
        return format_success("Tables listed", data={"project_id": project_id, "dataset_id": dataset_id, "tables": table_list})
    except Exception as e: return handle_gcp_error(e, f"listing BQ tables dataset {project_id}:{dataset_id}")

async def bq_get_table_schema( arguments: Dict[str, Any], conn_id: str, bq_job_store: FirestoreBqJobStore, **kwargs ) -> McpToolReturnType:
    """Gets schema required BQ table"""
    project_id = arguments.get("project_id"); dataset_id = arguments.get("dataset_id"); table_id = arguments.get("table_id")
    # Simplified validation assumes IDs are mandatory args now
    if not project_id or not isinstance(project_id, str): return format_error("Missing invalid project id")
    if not dataset_id or not isinstance(dataset_id, str): return format_error("Missing invalid dataset id")
    if not table_id or not isinstance(table_id, str): return format_error("Missing invalid table id")
    # Table ID parsing logic removed assumes simple table ID with required project/dataset args
    if '.' in table_id: return format_error("Table id should be simple name project dataset provided separately")

    try:
        client = get_bq_client(); table_ref_str = f"{project_id}.{dataset_id}.{table_id}"
        table_ref = bigquery.TableReference.from_string(table_ref_str)
        table = await asyncio.to_thread(_get_table_sync, client, table_ref)
        schema_list = [{"name": f.name, "type": f.field_type, "mode": f.mode} for f in table.schema]
        return format_success("Schema retrieved", data={"project_id": table.project, "dataset_id": table.dataset_id, "table_id": table.table_id, "schema": schema_list})
    except google_exceptions.NotFound: return format_error(f"Table {table_ref_str} not found")
    except Exception as e: return handle_gcp_error(e, f"getting schema table {table_ref_str}")

async def bq_submit_query( arguments: Dict[str, Any], conn_id: str, bq_job_store: FirestoreBqJobStore, **kwargs ) -> McpToolReturnType:
    """Submits BQ query job asynchronously returns job ID uses Firestore"""
    query_str = arguments.get("query"); # ... validation ...
    if not query_str or not isinstance(query_str, str): return format_error("Missing invalid query string")
    project_id_arg = arguments.get("project_id"); # ... validation ...
    default_project_id_arg = arguments.get("default_dataset_project_id"); # ... validation ...
    default_dataset_id_arg = arguments.get("default_dataset_id"); # ... validation ...

    target_project = project_id_arg # Project run job in
    job_default_dataset_ref: Optional[bigquery.DatasetReference] = None
    if default_project_id_arg and default_dataset_id_arg:
         job_default_dataset_ref = bigquery.DatasetReference(default_project_id_arg, default_dataset_id_arg)

    try:
        client = get_bq_client();
        if not target_project: target_project = client.project
        job_config = bigquery.QueryJobConfig(use_legacy_sql=False);
        if job_default_dataset_ref: job_config.default_dataset = job_default_dataset_ref
        logger.info(f"Submitting BQ Job Project {target_project} Query {query_str[:50]}", extra={"conn_id": conn_id})
        query_job = await asyncio.to_thread(_submit_job_sync, client, query_str, job_config, target_project)
        job_id = query_job.job_id; location = query_job.location; initial_state = query_job.state
        logger.info(f"BQ Job submitted {job_id} Location {location} State {initial_state}", extra={"conn_id": conn_id})
        # --- Store Job Info Firestore ---
        job_info = BqJobInfo(job_id=job_id, location=location, conn_id=conn_id, status=initial_state)
        await bq_job_store.add_job(job_info) # Uses Firestore store now
        # --------------------------------
        return format_success("Query submitted Use bq get job status poll", data={"job_id": job_id, "location": location, "state": initial_state})
    except google_exceptions.BadRequest as e: return handle_gcp_error(e, "submitting query BadRequest")
    except google_exceptions.Forbidden as e: return handle_gcp_error(e, "submitting query Forbidden")
    except Exception as e: return handle_gcp_error(e, f"submitting BQ query")

async def bq_get_job_status( arguments: Dict[str, Any], conn_id: str, bq_job_store: FirestoreBqJobStore, **kwargs ) -> McpToolReturnType:
    """Checks job status via Firestore if DONE Success fetches first page results"""
    job_id = arguments.get("job_id"); # ... validation ...
    if not job_id or not isinstance(job_id, str): return format_error("Missing invalid job id")
    # Location arg is mainly for fallback API call if needed now
    location_arg = arguments.get("location"); # ... validation ...

    logger.debug(f"Getting job status from Firestore {job_id}", extra={"conn_id": conn_id})
    job_info = await bq_job_store.get_job(job_id) # Reads from Firestore

    if not job_info:
        # Optional Fallback check BQ API directly if not found in Firestore
        # logger.warning(f"Job {job_id} not found Firestore trying direct API lookup", extra={"conn_id": conn_id})
        # try: client=get_bq_client(); job = await asyncio.to_thread(_get_job_sync, client, job_id, location_arg); job_info = BqJobInfo(...) # Reconstruct if needed
        # except google_exceptions.NotFound: return format_error(...)
        # except Exception as e: return handle_gcp_error(...)
        # If still not found after fallback
        return format_error(f"Job {job_id} not found tracked")

    status_data = {"job_id": job_info.job_id, "location": job_info.location, "state": job_info.status, "error_result": job_info.error_result}

    if job_info.status == 'DONE':
        if job_info.error_result: return format_error(f"Job {job_id} finished errors", data=status_data)
        else:
            # --- Job Done Successfully Fetch FIRST page results ---
            logger.info(f"Job {job_id} DONE Fetching first page results", extra={"conn_id": conn_id})
            try:
                client = get_bq_client(); max_results_first_page = 1000
                # Use retry wrapped helper fetch page
                schema, rows, token, total = await asyncio.to_thread(
                    _list_rows_sync, client, job_id, job_info.location, None, max_results_first_page # page token None
                )
                schema_list = [{"name": f.name, "type": f.field_type} for f in schema]; rows_list = [_serialize_row(r) for r in rows]
                status_data["schema"] = schema_list; status_data["rows"] = rows_list; status_data["next_page_token"] = token; status_data["total_rows"] = total
                return format_success(f"Job {job_id} completed Returning first page results", data=status_data)
            except Exception as e:
                logger.error(f"Error fetching first page results completed job {job_id} {e}", exc_info=True, extra={"conn_id": conn_id})
                # Return DONE status indicate result fetch error
                return format_error(f"Job {job_id} completed but failed fetch first page results {e}", data = {**status_data, "rows": None, "schema": None, "next_page_token": None}) # type ignore
    else:
        # Job PENDING or RUNNING
        logger.info(f"Job {job_id} still {job_info.status}", extra={"conn_id": conn_id})
        return format_info(f"Job {job_id} currently {job_info.status}", data=status_data)


async def bq_get_query_results( arguments: Dict[str, Any], conn_id: str, bq_job_store: FirestoreBqJobStore, **kwargs ) -> McpToolReturnType:
    """Fetches specific page results completed BQ query job requires page token"""
    job_id = arguments.get("job_id"); page_token = arguments.get("page_token"); location_arg = arguments.get("location")
    # Validation
    if not job_id or not isinstance(job_id, str): return format_error("Missing invalid job id")
    if not page_token or not isinstance(page_token, str): return format_error("Missing invalid required argument page token fetch subsequent pages")
    if location_arg is not None and not isinstance(location_arg, str): return format_error("Invalid location")
    try: max_results = int(arguments.get("max_results", 1000)); # ... range check ...
    except (ValueError, TypeError): max_results = 1000

    # Determine location argument > stored job info > error
    location = location_arg
    if not location:
        job_info = await bq_job_store.get_job(job_id) # Read from Firestore
        if job_info: location = job_info.location
        else: return format_error(f"Cannot fetch results page Location job {job_id} unknown Please provide location")
    if not location: return format_error(f"Cannot fetch results page Location job {job_id} could not be determined")

    try:
        client = get_bq_client()
        logger.debug(f"Getting results page BQ job {job_id} Loc {location} PageToken {page_token[:10]}", extra={"conn_id": conn_id})
        # Fetch requested page retry wrapped helper
        schema, rows, token, total = await asyncio.to_thread(
            _list_rows_sync, client, job_id, location, page_token, max_results
        )
        schema_list = [{"name": f.name, "type": f.field_type} for f in schema]; rows_list = [_serialize_row(r) for r in rows]
        return format_success("Query results page retrieved", data={"job_id": job_id, "location": location, "schema": schema_list, "rows": rows_list, "next_page_token": token, "total_rows": total})
    except google_exceptions.NotFound: return format_error(f"Job {job_id} not found or invalid page token")
    except Exception as e: return handle_gcp_error(e, f"getting results page job {job_id}")


def _serialize_row(row: bigquery.table.Row) -> Dict[str, Any]:
    """Helper convert BQ Row JSON serializable dict"""
    row_dict = {}; # ... implementation unchanged ...
    for key, value in row.items():
         if isinstance(value, bytes):
             try: row_dict[key] = value.decode('utf-8')
             except UnicodeDecodeError: row_dict[key] = f"<bytes:{len(value)}>"
         else: row_dict[key] = value
    return row_dict
