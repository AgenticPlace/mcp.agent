> **⚠️ Disclaimer:** This documentation describes a *hypothetical* tool, `mcp.agent` (v1.0.0). The codebase provided is a functional proof-of-concept demonstrating **stateless context**, **Firestore-backed async BQ job tracking**, GCS Signed URLs, and basic environment variable handling. It requires comprehensive testing, security hardening, and feature refinement for production use.

# `mcp.agent`: Simplified & Scalable GCP Integration for MCP Agents (v1.0.0)

`mcp.agent` is a command-line tool designed to significantly ease the integration of common Google Cloud services – specifically **Google Cloud Storage (GCS)** and **BigQuery (BQ)** – into applications using the **Model Context Protocol (MCP)**.

This **v1.0.0** milestone focuses on **scalability and robustness** by:

*   Adopting a **stateless design** regarding user context (buckets/datasets). Clients must now provide necessary identifiers in each relevant call.
*   Persisting **BigQuery job state** in **Google Cloud Firestore** for durability across server instances and restarts.
*   Utilizing **GCS Signed URLs** for efficient, scalable large file transfers.
*   Implementing an **asynchronous pattern for BigQuery queries** with server-side polling updates stored in Firestore.

It automates the creation and management of a specialized MCP server, exposing GCS and BQ functionalities as standard MCP tools.

## Problem Solved

Integrating cloud services often involves boilerplate. `mcp.agent` simplifies common GCS/BQ tasks by providing pre-built tools, handling server-side auth (ADC), and using scalable cloud patterns (Signed URLs, Firestore), while removing the scalability bottleneck of in-memory connection state.

## Core Features (v1.0.0)

*   🚀 **Automated Server Launch:** Single command (`mcp-agent`) starts the MCP server.
*   🛠️ **Focused GCP Toolset:** Pre-built tools for GCS (buckets, object listing) and BigQuery (datasets, tables, async queries). **Context tools are removed.**
*   🔗 **GCS Signed URLs:** Scalable large file reads/writes via direct client-GCS interaction.
*   ⏳ **Async BigQuery Queries with Firestore State:** Submits BQ queries, tracks status persistently in Firestore (polled by server), allows clients to check status and retrieve paginated results.
*   ✅ **Stateless Context:** Server no longer holds per-connection bucket/dataset defaults, improving scalability and simplifying deployment. **Clients must provide identifiers.**
*   🧩 **Standard MCP Interface:** Compatible with any MCP client (`list_tools`, `call_tool`).
*   🔒 **Server-Side Authentication:** Uses Application Default Credentials (ADC).
*   🔑 **Environment-Based Config:** Manages optional SSE API key via `.env`/env vars (`python-dotenv`, Secret Manager support).
*   🌐 **Flexible Transports:** Supports `stdio` and `sse`.

## How it Works (v1.0.0 Technical Overview)

1.  **CLI (`cli.py`):** Loads `.env`, parses args, determines API key (checking Secret Manager env var first, then direct env var), performs GCP client pre-flight checks (including Firestore), starts server transport.
2.  **MCP Server Core (`server.py`):** Manages MCP connections. **No longer holds user context.** Uses `FirestoreBqJobStore` for BQ job state. Runs background BQ poller task (reading from/writing to Firestore). Routes `call_tool` requests, injecting the job store where needed.
3.  **GCP Tool Implementations (`gcp_tools/*.py`):**
    *   GCS tools (`gcs_get_read_signed_url`, `gcs_get_write_signed_url`, `gcs_list_objects`, etc.) now **require** `bucket_name` argument. They generate Signed URLs or perform actions directly using provided IDs.
    *   BQ tools (`bq_list_tables`, `bq_get_table_schema`, etc.) now **require** `project_id`/`dataset_id`.
    *   BQ async pattern:
        *   `bq_submit_query`: Starts BQ job, saves `job_id`, `location`, etc. to Firestore via `FirestoreBqJobStore`, returns job info.
        *   `bq_get_job_status`: Reads job status *from Firestore* (updated by background poller). If DONE+Success, fetches and returns the *first page* of results directly from BQ.
        *   `bq_get_query_results`: Fetches subsequent pages of results directly from BQ using `page_token`.
    *   Blocking GCP SDK calls use `asyncio.to_thread`. Retries are applied via `tenacity`.
4.  **BQ Job Management (`job_store.py`):**
    *   `FirestoreBqJobStore` interacts with Firestore (Datastore mode) to `add`, `get`, `update`, and `query` BQ job status records, using `job_id` as the document ID. Provides durability.

## Prerequisites

1.  Python 3.9+
2.  GCP Project (Billing Enabled)
3.  **Enabled APIs:**
    *   Cloud Storage API
    *   BigQuery API
    *   **Firestore API** (ensure Firestore database is created in Datastore mode in your project)
    *   **Secret Manager API** (if using secret for API key)
4.  **Authentication (ADC):** Environment running `mcp-agent` needs ADC configured (`gcloud auth application-default login` or Service Account).
5.  **IAM Permissions:** The Service Account running `mcp.agent` needs roles like:
    *   GCS roles (e.g., `roles/storage.objectViewer`, `roles/storage.objectCreator`)
    *   BigQuery roles (e.g., `roles/bigquery.jobUser`, `roles/bigquery.dataViewer`)
    *   **Firestore roles** (e.g., `roles/datastore.user`)
    *   `roles/secretmanager.secretAccessor` (if using Secret Manager for API key)
    *   `roles/iam.serviceAccountTokenCreator` on *itself* (needed for generating Signed URLs)
6.  MCP Client Library (if not using ADK)
7.  ADK Setup (Optional)

## Installation

1.  **Python Dependencies:**
    ```bash
    pip install model-context-protocol google-cloud-storage google-cloud-bigquery python-dotenv python-json-logger google-cloud-secret-manager tenacity google-cloud-firestore
    ```
2.  **Install `mcp.agent` Tool:**
    *(Assuming source code)*
    ```bash
    cd path/to/mcp_agent_source && pip install .
    ```

## Usage

### 1. Running the `mcp.agent` Server

*(Command structure remains the same, but behavior is now stateless regarding user context)*

```bash
# Example: Stateless server via SSE on port 8080
mcp-agent --tools storage,bigquery --port 8080 --require-api-key
Use code with caution.
Markdown
(Remember to set MCP_AGENT_API_KEY_SECRET_NAME or MCP_AGENT_API_KEY in .env or environment if using --require-api-key)
➡️ Note connection details from server output.
2. Connecting Clients
(Connection setup is the same, client interaction logic changes due to statelessness)
3. Agent Interaction Logic (v1.0.0 - Stateless Pattern)
Instruct your agent (LLM or otherwise) to:
✅ Check Status: Always parse JSON response, check "status".
🔑 Provide Identifiers: Always include bucket_name, project_id, dataset_id arguments when calling tools like gcs_list_objects, gcs_get_read_signed_url, bq_list_tables, bq_get_table_schema, etc. The server no longer remembers defaults.
🔗 GCS Signed URLs: Use gcs_get_read_signed_url / gcs_get_write_signed_url. Tell the user/app to perform the HTTP GET/PUT on the "signed_url".
⏳ BQ Async Polling:
bq_submit_query -> Get job_id/location. Client must store these.
bq_get_job_status (repeat) -> Check "state".
If "state" is "DONE" & "status" is "success", process first page data ("rows", "schema") from this status response. Check "next_page_token".
If "next_page_token", call bq_get_query_results with token for page 2+. Repeat.
If "state" is "ERROR", report error.
📢 Report Errors: Use the "message" field from error responses.
Tool Reference (v1.0.0 Changes)
REMOVED: gcs_set_context_bucket, gcs_clear_context_bucket, bq_set_context_dataset, bq_clear_context_dataset.
REQUIRED ARGS: bucket_name, project_id, dataset_id are now mandatory for most GCS/BQ tools that operate on specific resources.
GCS: gcs_list_buckets, gcs_list_objects, gcs_get_read_signed_url, gcs_get_write_signed_url, gcs_write_string_object.
BQ: bq_list_datasets, bq_list_tables, bq_get_table_schema, bq_submit_query, bq_get_job_status, bq_get_query_results.
(See source code gcp_tools/__init__.py for full schemas).
⚠️ Limitations (v1.0.0 Highlights)
Stateless Context: Simplifies scaling but places burden on the client to manage context and provide identifiers on every relevant call.
Client Complexity: Async BQ requires client polling. Signed URLs require client HTTP handling.
Firestore Dependency: Requires Firestore setup and appropriate IAM permissions. BQ job state is now durable but relies on another GCP service. Potential cost implications for high job volume.
Narrow Scope: Only GCS and BQ.
Basic Functionality: Omits advanced GCP features.
ADC Auth Only: No user impersonation.
Scalability: Statelessness improves scalability, but requires load balancing and orchestration infrastructure. Background poller might become a bottleneck at extreme scale (consider Cloud Tasks/Functions).
Minimal Security: Relies on ADC permissions, network security, transport security (HTTPS), and optional basic API key. Not fully production hardened.
Critical: Consult the detailed Limitations.md document (updated for v1.0.0) for a comprehensive understanding before using this PoC in sensitive environments.
License
(Example: Apache License 2.0)
