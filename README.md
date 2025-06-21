> **⚠️ Disclaimer:** This documentation describes `mcp.agent` (v1.0.0). The codebase provided is a functional proof-of-concept demonstrating **stateless context**, **Firestore-backed asynchronous BigQuery job tracking**, GCS Signed URLs, and basic environment variable handling. It requires comprehensive testing, security hardening, and feature refinement before any consideration for production use.

# `mcp.agent`: Simplified & Scalable GCP Integration for MCP Agents (v1.0.0)

`mcp.agent` is a command-line tool designed to significantly ease the integration of common Google Cloud Platform (GCP) services – specifically **Google Cloud Storage (GCS)** and **BigQuery (BQ)** – into applications using the **Model Context Protocol (MCP)**.

This **v1.0.0** milestone focuses on enhancing **scalability and robustness** by:

*   Adopting a **stateless design**. Clients must provide necessary resource identifiers (e.g., bucket name, dataset ID) in each relevant tool call. Context-setting tools are removed.
*   Persisting **BigQuery job state** in **Google Cloud Firestore**, enabling job status tracking across server instances and restarts.
*   Utilizing **GCS Signed URLs** for efficient and scalable large file transfers directly between the client and GCS.
*   Implementing an **asynchronous pattern for BigQuery queries**, with server-side polling of job status and updates to Firestore.

The tool provides an MCP server that exposes GCS and BQ functionalities as standard MCP tools.

## Problem Solved

Integrating cloud services often involves repetitive boilerplate and complex authentication. `mcp.agent` simplifies this by:

*   Providing pre-built, stateless MCP tools for common GCS and BQ operations.
*   Handling server-side authentication using Google Cloud's Application Default Credentials (ADC).
*   Employing scalable cloud patterns like Signed URLs and Firestore-backed job tracking.
*   Removing scalability bottlenecks associated with in-memory connection state.

## Core Features (v1.0.0)

*   🚀 **Automated Server Launch:** Single command (`mcp-agent`) starts the MCP server.
*   🛠️ **Stateless GCP Toolset:**
    *   **GCS:** List buckets, list objects, generate V4 signed URLs for read/write, write string to object.
    *   **BigQuery:** List datasets, list tables, get table schema, submit asynchronous queries, get job status, retrieve paginated query results.
    *   *Context-setting tools (e.g., `gcs_set_context_bucket`) are removed.*
*   🔗 **GCS Signed URLs:** Scalable large file transfers via direct client-GCS interaction.
*   ⏳ **Async BigQuery Queries with Firestore State:**
    *   Submits BQ queries and tracks status persistently in Firestore via `FirestoreBqJobStore`.
    *   A background poller (`bq_poller.py`) updates job statuses in Firestore.
    *   Clients can check job status (`bq_get_job_status`) and retrieve paginated results (`bq_get_query_results`).
*   ✅ **Stateless Server:** Enhances scalability and simplifies deployment. Clients must provide all resource identifiers.
*   🧩 **Standard MCP Interface:** Compatible with any MCP client (`list_tools`, `call_tool`).
*   🔒 **Server-Side Authentication:** Uses Application Default Credentials (ADC).
*   🔑 **Environment-Based Configuration:** Manages SSE API key via `.env` or environment variables (supports Google Secret Manager). GCP project for Firestore can be set via `GCP_PROJECT` env var.
*   🌐 **Flexible Transports:** Supports `stdio` and `sse` (Server-Sent Events via `aiohttp`).
*   📝 **JSON Logging:** Uses `python-json-logger` for structured logging.

## How it Works (v1.0.0 Technical Overview)

1.  **Command-Line Interface (`mcp_agent/cli.py`):**
    *   Sole entry point for the agent (`mcp-agent` command).
    *   Loads `.env` variables. Sets up JSON logging.
    *   Parses arguments (tools, port, host, API key requirement, BQ poll interval).
    *   Handles API key retrieval (direct env var or Google Secret Manager).
    *   Performs pre-flight checks for GCP client readiness (GCS, BigQuery, Firestore, Secret Manager if used).
    *   If BigQuery tools are enabled:
        *   Initializes `FirestoreBqJobStore` (`mcp_agent/job_store.py`).
        *   Initializes the BigQuery client.
        *   Starts the background BigQuery job poller (`mcp_agent/bq_poller.py`) as an asyncio task.
    *   Calls core server functions from `mcp_agent/server.py` to start listening on `stdio` or `sse`.

2.  **MCP Server Core (`mcp_agent/server.py`):**
    *   `run_stdio_server`: Handles MCP communication over standard input/output. Reads JSON messages, calls `dispatch_tool`, writes JSON responses.
    *   `run_sse_server`: Uses `aiohttp` to run an HTTP server for Server-Sent Events.
        *   Provides an `/mcp` endpoint for POST requests.
        *   Includes middleware for API key authentication if configured.
        *   Parses MCP JSON message from request, calls `dispatch_tool`, streams MCP `Content` objects back as SSE events.
    *   `dispatch_tool`: Central function that receives parsed MCP messages.
        *   Looks up the tool function in `ALL_TOOLS_MAP` (defined in `mcp_agent/gcp_tools/__init__.py`).
        *   Calls the appropriate tool function, passing arguments, `conn_id`, and the `FirestoreBqJobStore` instance (if BQ tools are enabled).

3.  **GCP Tool Implementations (`mcp_agent/gcp_tools/`):**
    *   `__init__.py`: Defines `ALL_TOOLS_MAP`, mapping tool string names to their respective asynchronous function implementations in `storage.py` and `bigquery.py`. (Tool schemas for advertisement are TBD).
    *   `storage.py` (GCS Tools):
        *   Implements `gcs_list_buckets`, `gcs_list_objects`, `gcs_get_read_signed_url`, `gcs_get_write_signed_url`, `gcs_write_string_object`.
        *   Uses `google-cloud-storage` client, with blocking calls wrapped in `asyncio.to_thread`.
        *   Signed URL functions generate GCS V4 signed URLs.
    *   `bigquery.py` (BigQuery Tools):
        *   Implements `bq_list_datasets`, `bq_list_tables`, `bq_get_table_schema`, `bq_submit_query`, `bq_get_job_status`, `bq_get_query_results`.
        *   Uses `google-cloud-bigquery` client, with blocking calls wrapped in `asyncio.to_thread`.
        *   `bq_submit_query`: Creates a job in BQ and records its initial state in Firestore via `FirestoreBqJobStore`.
        *   `bq_get_job_status`: Reads job status from Firestore. If the job is DONE and successful, it can also return the first page of results.
        *   `bq_get_query_results`: Fetches subsequent pages of results for a completed job.
    *   Both modules use helper functions from `mcp_agent/utils.py` for response formatting and GCP error handling (including retries via `tenacity`).

4.  **BigQuery Job Store (`mcp_agent/job_store.py`):**
    *   Defines `BqJobInfo` dataclass to represent job details.
    *   `FirestoreBqJobStore` class:
        *   Uses `google-cloud-firestore` async client.
        *   Methods: `add_job`, `get_job`, `update_job_status`, `query_pending_jobs`.
        *   Handles serialization/deserialization of `BqJobInfo` to/from Firestore.

5.  **BigQuery Poller (`mcp_agent/bq_poller.py`):**
    *   `run_bq_job_poller` function runs as a background asyncio task.
    *   Periodically calls `firestore_job_store.query_pending_jobs()`.
    *   For each pending job, calls the BigQuery API to get its current status.
    *   Updates the job's record in Firestore via `firestore_job_store.update_job_status()`.

## Prerequisites

1.  **Python:** Version 3.9+
2.  **GCP Project:** Billing enabled.
    *   **Enabled APIs:** Cloud Storage, BigQuery, **Firestore API** (ensure Firestore DB is created, preferably in Datastore mode), Secret Manager API (if used for API key).
3.  **Authentication (ADC):** Configured via `gcloud auth application-default login` or service account.
4.  **IAM Permissions for the agent's service account:**
    *   GCS: `roles/storage.objectViewer`, `roles/storage.objectCreator`. `roles/iam.serviceAccountTokenCreator` (on the SA itself for signed URLs).
    *   BigQuery: `roles/bigquery.jobUser`, `roles/bigquery.dataViewer`.
    *   Firestore: `roles/datastore.user`.
    *   Secret Manager: `roles/secretmanager.secretAccessor` (if used).
5.  MCP Client library/tool.

## Installation

1.  **Install Python Dependencies:**
    ```bash
    pip install model-context-protocol google-cloud-storage google-cloud-bigquery google-cloud-firestore google-cloud-secret-manager python-dotenv python-json-logger tenacity aiohttp aiohttp-sse
    ```
2.  **Install `mcp.agent` (from source):**
    ```bash
    cd path/to/mcp_agent_source
    pip install .
    ```

## Usage

### 1. Running the `mcp.agent` Server

**Example (SSE on port 8080, API key required, custom BQ poll interval):**
```bash
export GCP_PROJECT="your-gcp-project-id" # For FirestoreBqJobStore if not default
export MCP_AGENT_API_KEY="your-secret-api-key" # Or use MCP_AGENT_API_KEY_SECRET_NAME

mcp-agent --tools storage,bigquery --port 8080 --require-api-key --bq-poll-interval 30
```
*   Set `MCP_AGENT_API_KEY_SECRET_NAME` (full Secret Manager secret version path) or `MCP_AGENT_API_KEY` if using `--require-api-key`.
*   The `GCP_PROJECT` environment variable can specify the project for Firestore if it differs from the ADC default.

➡️ *Note connection details from server output.*

### 2. Agent Interaction Logic (v1.0.0 - Stateless Pattern)

*   ✅ **Check Status:** Always parse the JSON response, check the `"status"` field.
*   🔑 **Provide Identifiers:** Always include `bucket_name`, `object_name` (for GCS) or `project_id`, `dataset_id`, `table_id`, `job_id`, `location` (for BQ) as required by each tool.
*   🔗 **GCS Signed URLs:** Use `gcs_get_read_signed_url` / `gcs_get_write_signed_url`. The client performs the HTTP GET/PUT on the returned `"signed_url"`.
*   ⏳ **BQ Async Polling Workflow:**
    1.  Call `bq_submit_query` (args: `query`, optional `project_id`). Get `job_id`, `location`.
    2.  Periodically call `bq_get_job_status` (args: `job_id`, `location`). Check `"state"`.
    3.  If `"state"` is `"DONE"` & response `"status"` is `"success"`:
        *   Process results from `bq_get_job_status` response (first page: `"rows"`, `"schema"`).
        *   Check for `"next_page_token"`.
    4.  If `"next_page_token"`, call `bq_get_query_results` (args: `job_id`, `location`, `page_token`) for subsequent pages.
    5.  If BQ job state is `"ERROR"` or tool call status is error, use `"message"` and `"error_result"` from response.
*   📢 **Report Errors:** Use the `"message"` (and potentially `"data.error_result"`) from error responses.

## Tool Reference (v1.0.0 Implemented Tools)

This list reflects the implemented stateless tools. (Context-setting tools are REMOVED). For detailed arguments, refer to the source or future schema definitions.

**GCS Tools (`mcp_agent/gcp_tools/storage.py`):**
*   `gcs_list_buckets`: Lists GCS buckets.
    *   Args: `project_id` (optional).
*   `gcs_list_objects`: Lists objects in a bucket.
    *   Args: `bucket_name` (required), `prefix` (optional), `delimiter` (optional).
*   `gcs_get_read_signed_url`: Generates a V4 signed URL for reading an object.
    *   Args: `bucket_name` (required), `object_name` (required), `expiration_minutes` (optional, default 60).
*   `gcs_get_write_signed_url`: Generates a V4 signed URL for writing an object.
    *   Args: `bucket_name` (required), `object_name` (required), `expiration_minutes` (optional, default 60), `content_type` (optional), `headers` (optional dict).
*   `gcs_write_string_object`: Writes a string directly to a GCS object.
    *   Args: `bucket_name` (required), `object_name` (required), `content` (string, required), `content_type` (optional).

**BigQuery Tools (`mcp_agent/gcp_tools/bigquery.py`):**
*   `bq_list_datasets`: Lists datasets in a project.
    *   Args: `project_id` (optional, defaults to client's project).
*   `bq_list_tables`: Lists tables in a dataset.
    *   Args: `project_id` (required), `dataset_id` (required).
*   `bq_get_table_schema`: Gets the schema of a table.
    *   Args: `project_id` (required), `dataset_id` (required), `table_id` (required).
*   `bq_submit_query`: Submits a query for asynchronous execution.
    *   Args: `query` (SQL string, required), `project_id` (optional, for job's billing project), `default_dataset_project_id` (optional), `default_dataset_id` (optional for unqualified table names in query).
    *   Returns: `job_id`, `location`, initial `state`.
*   `bq_get_job_status`: Checks a job's status (from Firestore).
    *   Args: `job_id` (required), `location` (optional, but recommended).
    *   Returns: Job status details. If DONE & success, may include first page of results.
*   `bq_get_query_results`: Fetches paginated results for a completed job.
    *   Args: `job_id` (required), `page_token` (required), `location` (optional but recommended), `max_results` (optional).

*(Refer to source code in `mcp_agent/gcp_tools/*.py` for exact argument names and behavior. Schemas for MCP advertisement TBD.)*

## ⚠️ Limitations (v1.0.0 Highlights)

*   **Stateless Context Burden:** Clients must manage and send all identifiers.
*   **Increased Client Complexity:** Async BQ polling and Signed URL handling require client-side logic.
*   **Firestore Dependency & Cost:** Requires Firestore setup and may incur costs.
*   **Narrow Service Scope:** Only selected GCS and BigQuery operations.
*   **Basic Cloud Functionality:** Omits many advanced GCP features.
*   **ADC Auth Only:** No user impersonation.
*   **Scalability Considerations:** Production deployments need load balancing. BQ poller might be a bottleneck at extreme scale (consider Cloud Tasks/Functions).
*   **Minimal Security Hardening:** PoC not fully hardened for production.

**Critical Note:** `mcp.agent` v1.0.0 is a proof-of-concept. Consult `docs/LIMITATIONS.md` for a comprehensive understanding before use in sensitive environments.

## Contributing

This project is currently a proof-of-concept. While formal contributions are not being solicited at this stage, feedback and suggestions are welcome via issues on the project's repository (if applicable).

## License

(Example: Apache License 2.0 - Please replace with your chosen license)
