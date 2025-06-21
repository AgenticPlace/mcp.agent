# Explanation of the `mcp.agent` Project (v1.0.0 - Intended)

This document provides an explanation of the `mcp.agent` project, based on its `README.md` (which describes v1.0.0), the existing codebase, and identified discrepancies/missing components.

## 1. Intended Purpose and Architecture (v1.0.0)

As per the `README.md`, `mcp.agent` v1.0.0 is designed as a command-line tool to simplify the integration of Google Cloud services (specifically Google Cloud Storage - GCS, and BigQuery - BQ) into applications using the Model Context Protocol (MCP).

The key architectural features for v1.0.0 are:

*   **Stateless Design:** The server does not hold per-connection context (like default GCS buckets or BQ datasets). Clients must provide necessary identifiers (e.g., `bucket_name`, `project_id`, `dataset_id`) in each relevant tool call. This is intended to improve scalability.
*   **GCS Signed URLs:** For large file transfers to/from GCS, the agent is meant to provide GCS Signed URLs. This allows clients to interact directly and securely with GCS, offloading bandwidth from the agent.
*   **Asynchronous BigQuery Queries:** BigQuery queries are submitted asynchronously. The agent starts the BQ job, and the client is expected to poll for its status.
*   **Firestore for BigQuery Job State Persistence:** The status and metadata of asynchronous BigQuery jobs are persisted in Google Cloud Firestore. This provides durability for job tracking across agent restarts or scaled instances.
*   **Server-Side Authentication:** Uses Application Default Credentials (ADC) for authenticating with GCP services.
*   **Focused Toolset:** Provides pre-built MCP tools for common GCS and BQ operations, adapted for the stateless and async patterns.

## 2. Codebase Structure and Components

### 2.1. Entry Point

*   **`mcp_agent/cli.py`:** This is the main command-line interface for the agent. It handles:
    *   Parsing command-line arguments (e.g., enabled tools, connection mode - STDIO/SSE, port, API key).
    *   Setting up logging.
    *   Performing pre-flight checks for GCP client initialization (including Firestore, if BQ is enabled).
    *   Starting the appropriate MCP server transport (STDIO or SSE).

### 2.2. Tool Definitions and Dispatch

*   **`mcp_agent/jobstore.py` (plural filename):** Despite its name, this file acts as the primary definition and aggregation point for the MCP tools that the agent exposes under the v1.0.0 specification. It contains:
    *   Schemas for GCS tools (e.g., `gcs_list_buckets`, `gcs_get_read_signed_url`, `gcs_get_write_signed_url`).
    *   Schemas for BigQuery tools (e.g., `bq_list_datasets`, `bq_submit_query`, `bq_get_job_status`, `bq_get_query_results`).
    *   A map (`ALL_TOOLS_MAP`) that links tool names to their implementation functions.
    *   It correctly imports GCS functions from a relative `.storage` module and BQ functions from a relative `.bigquery` module within the `mcp_agent/gcp_tools/` directory.

### 2.3. GCP Tool Implementations

*   **`mcp_agent/gcp_tools/` (directory):** This directory is intended to house the actual logic for interacting with GCP services.

    *   **BigQuery Tools (Async):**
        *   **Location:** The implementation for asynchronous BigQuery tools (e.g., `bq_submit_query`, `bq_get_job_status`) is currently located in the file `mcp_agent/gcp_tools/storage.py`.
        *   **This file is misnamed and should be `mcp_agent/gcp_tools/bigquery.py`.**
        *   The functions within correctly implement the asynchronous pattern, requiring explicit project/dataset IDs.
        *   Crucially, these functions attempt to import `FirestoreBqJobStore` from `..job_store` (i.e., from `mcp_agent/job_store.py`).

    *   **GCS Tools (Signed URLs):**
        *   **Status: MISSING / INACCESSIBLE.**
        *   The actual implementations for GCS tools that should provide signed URLs (e.g., `gcs_get_read_signed_url`, `gcs_get_write_signed_url`), which are expected to be in `mcp_agent/gcp_tools/storage.py`, could not be accessed. The path `mcp_agent/gcp_tools/storage.py` consistently returned the BigQuery tool implementations.

### 2.4. BigQuery Job State Persistence

*   **`FirestoreBqJobStore` class:**
    *   **Status: MISSING.**
    *   The `README.md` and the BigQuery tool implementations indicate that a class named `FirestoreBqJobStore` is responsible for interacting with Firestore to save, retrieve, and update the state of BigQuery jobs.
    *   A `grep` search for "class FirestoreBqJobStore" yielded no results, indicating this critical component is missing from the provided codebase.
    *   The import statement `from ..job_store import FirestoreBqJobStore` in the BigQuery tools implementation (currently in `mcp_agent/gcp_tools/storage.py`) will fail because this class is not defined in `mcp_agent/job_store.py` (plural) or any other discoverable location.

### 2.5. Utilities

*   **`mcp_agent/utils.py`:** Contains utility functions, likely for formatting MCP responses, error handling, retry decorators (`retry_on_gcp_transient_error`), and potentially GCP client initialization helpers.

## 3. Legacy/Conflicting Code

Several files appear to be from an older, stateful version of the agent, conflicting with the v1.0.0 stateless architecture described in the `README.md`:

*   **`mcp_agent/context.py`:** Defines a `ConnectionContextManager` class for managing GCS bucket and BQ dataset context per connection. This is not used by or compatible with the v1.0.0 stateless tool design.
*   **`mcp_agent/gcp_tools/__init__.py`:** The version of this file explored during the review defines tool schemas and imports for stateful operations (e.g., `gcs_set_context_bucket`, synchronous `bq_query`) and attempts to import from a non-existent `mcp_agent/gcp_tools/bigquery.py` (for stateful BQ tools). This file does not align with the v1.0.0 toolset defined in `mcp_agent/jobstore.py`.
*   **`mcp_agent/server.py`:** This file appears to be a largely redundant or older version of `mcp_agent/cli.py`, containing similar logic for argument parsing and server setup. `cli.py` is the correct entry point as per the README.

## 4. Data Flow (Intended for v1.0.0)

1.  User starts the agent via `mcp-agent` (invoking `mcp_agent/cli.py`).
2.  Agent initializes, sets up MCP server (STDIO or SSE).
3.  MCP Client connects and sends a `list_tools` request.
4.  Agent responds with tools defined in `mcp_agent/jobstore.py` (which should reflect GCS Signed URL and Async BQ tools).
5.  Client calls a tool, e.g., `bq_submit_query` with `query`, `project_id`, etc.
6.  The call is dispatched via `ALL_TOOLS_MAP` in `mcp_agent/jobstore.py` to the relevant function in `mcp_agent/gcp_tools/bigquery.py` (currently misnamed `storage.py`).
7.  The `bq_submit_query` function:
    *   Uses the GCP BigQuery client to start the query job.
    *   *Would* use an instance of `FirestoreBqJobStore` to create a record in Firestore with the `job_id`, `location`, and initial status.
    *   Returns the `job_id` and `location` to the client.
8.  Client polls using `bq_get_job_status` with the `job_id`.
9.  The `bq_get_job_status` function:
    *   *Would* query Firestore via `FirestoreBqJobStore` to get the current job status.
    *   If the job is DONE and successful, it *would* also fetch the first page of results from BigQuery directly and include it in the response.
10. For GCS operations like `gcs_get_read_signed_url`:
    *   The corresponding function in `mcp_agent/gcp_tools/storage.py` (actual GCS tools, currently missing/inaccessible) *would* generate a signed URL.
    *   The signed URL is returned to the client, which then uses it to download the file directly from GCS.

## 5. Dependencies

*   `google-cloud-storage`
*   `google-cloud-bigquery`
*   `google-cloud-firestore` (implied by design, but `FirestoreBqJobStore` is missing)
*   `model-context-protocol`
*   `python-dotenv`
*   `python-json-logger`
*   `google-cloud-secret-manager` (for API key management)
*   `tenacity` (for retries)

## 6. Current State and Functionality Issues

As of the current state of the codebase reviewed:

*   **The agent is NOT functional as per the v1.0.0 `README.md` specification.**
*   **Critical Missing Component: `FirestoreBqJobStore`:** The absence of this class definition means that the asynchronous BigQuery functionality, a cornerstone of v1.0.0, cannot work. Any calls to `bq_submit_query` or `bq_get_job_status` would fail when trying to interact with the non-existent store.
*   **Critical Missing Component: GCS Signed URL Tools:** The actual implementations for GCS tools that generate signed URLs (expected in `mcp_agent/gcp_tools/storage.py`) are inaccessible or missing. The file at that path contains BigQuery logic instead. This means GCS functionality related to scalable file transfers is broken.
*   **File Misnaming:** `mcp_agent/gcp_tools/storage.py` contains BigQuery tool implementations and should be renamed to `mcp_agent/gcp_tools/bigquery.py`. This makes understanding and maintaining the codebase difficult.
*   **Legacy Code:** The presence of `context.py`, an outdated `gcp_tools/__init__.py`, and `server.py` adds confusion and dead code to the project.

**To make the project functional according to the v1.0.0 README, the following would be essential:**

1.  **Implement `FirestoreBqJobStore`:** Create the class with methods to add, get, and update BQ job information in Firestore. Ensure it's correctly placed so it can be imported by the BigQuery tools.
2.  **Provide Correct GCS Tool Implementations:** The actual GCS tools for generating signed URLs and other GCS operations need to be placed in `mcp_agent/gcp_tools/storage.py`.
3.  **Rename `mcp_agent/gcp_tools/storage.py` (current BQ code) to `mcp_agent/gcp_tools/bigquery.py`.**
4.  Ensure `mcp_agent/jobstore.py` (plural) correctly points to these fixed/added tool implementations.
5.  Remove or update legacy files to avoid confusion.

Without these changes, the agent primarily serves as a non-functional skeleton of its intended v1.0.0 design.
