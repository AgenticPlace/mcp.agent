> **⚠️ Disclaimer:** This documentation describes a *hypothetical* tool, `mcp.agent` (v1.0.0). The codebase provided is a functional proof-of-concept demonstrating **stateless context**, **Firestore-backed async BQ job tracking**, GCS Signed URLs, and basic environment variable handling. It requires comprehensive testing, security hardening, and feature refinement before any consideration for production use.

# `mcp.agent`: Simplified & Scalable GCP Integration for MCP Agents (v1.0.0)

`mcp.agent` is a command-line tool designed to significantly ease the integration of common Google Cloud Platform (GCP) services – specifically **Google Cloud Storage (GCS)** and **BigQuery (BQ)** – into applications using the **Model Context Protocol (MCP)**.

This **v1.0.0** milestone focuses on enhancing **scalability and robustness** by:

*   Adopting a **stateless design** regarding user context (e.g., GCS buckets, BigQuery datasets). Clients are now required to provide the necessary identifiers (like bucket name or dataset ID) in each relevant tool call.
*   Persisting **BigQuery job state** in **Google Cloud Firestore**. This ensures that job information is durable across server instances and restarts.
*   Utilizing **GCS Signed URLs** for efficient and scalable large file transfers, enabling direct client-to-GCS interaction.
*   Implementing an **asynchronous pattern for BigQuery queries**. The server polls for job completion status and updates Firestore, allowing clients to monitor progress without blocking.

The tool automates the creation and management of a specialized MCP server, exposing GCS and BQ functionalities as standard MCP tools.

## Problem Solved

Integrating cloud services like GCS and BigQuery into applications often involves writing repetitive boilerplate code and managing complex authentication flows. `mcp.agent` aims to simplify this by:

*   Providing pre-built MCP tools for common GCS and BQ operations.
*   Handling server-side authentication using Google Cloud's Application Default Credentials (ADC).
*   Employing scalable cloud patterns, such as Signed URLs for GCS access and Firestore for persistent BigQuery job tracking.
*   Removing the scalability bottleneck associated with in-memory connection state by adopting a fully stateless server architecture.

## Core Features (v1.0.0)

*   🚀 **Automated Server Launch:** A single command (`mcp-agent`) starts the MCP server, ready to handle client requests.
*   🛠️ **Focused GCP Toolset:** Offers pre-built tools for GCS (bucket and object operations) and BigQuery (dataset, table, and asynchronous query operations). *Context-setting tools (e.g., `gcs_set_context_bucket`) have been removed in v1.0.0 to enforce statelessness.*
*   🔗 **GCS Signed URLs:** Enables scalable large file reads and writes through direct client-GCS interaction using time-limited signed URLs.
*   ⏳ **Async BigQuery Queries with Firestore State:**
    *   Submits BigQuery queries and persistently tracks their status in Firestore.
    *   The server backend polls for job completion and updates the status in Firestore.
    *   Clients can periodically check the job status and retrieve paginated results once the query execution is complete and successful.
*   ✅ **Stateless Context:** The server does not maintain any per-connection defaults for GCS buckets or BigQuery datasets. This design enhances scalability and simplifies deployment in distributed environments. *Clients are responsible for providing all necessary resource identifiers (e.g., `bucket_name`, `project_id`, `dataset_id`) with each tool call.*
*   🧩 **Standard MCP Interface:** Fully compatible with any MCP client. Supports standard MCP operations like `list_tools` and `call_tool`.
*   🔒 **Server-Side Authentication:** Leverages Google Cloud's Application Default Credentials (ADC) for secure authentication to GCP services.
*   🔑 **Environment-Based Configuration:** Manages an optional Server-Sent Events (SSE) API key via `.env` files or environment variables, with built-in support for retrieval from Google Secret Manager.
*   🌐 **Flexible Transports:** Supports both `stdio` (standard input/output) and `sse` (Server-Sent Events) for communication between the client and the `mcp.agent` server.

## How it Works (v1.0.0 Technical Overview)

The `mcp.agent` operates through the following key components:

1.  **Command-Line Interface (`cli.py`):**
    *   Loads environment variables from a `.env` file (if present).
    *   Parses command-line arguments provided at startup.
    *   Determines the API key, prioritizing Google Secret Manager (if configured via `MCP_AGENT_API_KEY_SECRET_NAME`) over a direct environment variable (`MCP_AGENT_API_KEY`).
    *   Performs pre-flight checks to ensure GCP client libraries are configured correctly and Firestore is accessible.
    *   Starts the appropriate server transport mechanism (`stdio` or `sse`) to listen for client connections.
2.  **MCP Server Core (`server.py`):**
    *   Manages incoming MCP connections.
    *   Operates statelessly; no user-specific context (like default bucket or dataset) is stored on the server.
    *   Utilizes the `FirestoreBqJobStore` for creating, retrieving, and updating the state of BigQuery jobs in Firestore.
    *   Runs a background asynchronous task to periodically poll the status of active BigQuery jobs and updates their corresponding entries in Firestore.
    *   Routes `call_tool` requests from clients to the appropriate tool implementation, injecting dependencies like the job store where needed.
3.  **GCP Tool Implementations (`gcp_tools/*.py`):**
    *   **GCS Tools** (e.g., `gcs_get_read_signed_url`, `gcs_list_objects`):
        *   Now **require** a `bucket_name` argument for all operations targeting a specific bucket.
        *   Generate time-limited Signed URLs for file read/write operations or interact directly with GCS using the provided identifiers for other operations (like listing objects).
    *   **BQ Tools** (e.g., `bq_list_tables`, `bq_get_table_schema`):
        *   Now **require** `project_id` and `dataset_id` arguments for operations targeting specific datasets or tables.
    *   **BQ Asynchronous Pattern:**
        *   `bq_submit_query`: Initiates a BigQuery job, stores its `job_id`, `location`, and other relevant metadata in Firestore (via `FirestoreBqJobStore`), and returns this job information to the client.
        *   `bq_get_job_status`: Retrieves the job's current status *from Firestore*. The status in Firestore is kept up-to-date by the server's background poller. If the job is `DONE` and successful, this tool also fetches and returns the *first page* of query results directly from BigQuery.
        *   `bq_get_query_results`: Fetches subsequent pages of query results directly from BigQuery using a `page_token` provided from a previous `bq_get_job_status` or `bq_get_query_results` call.
    *   Blocking GCP SDK calls are executed in separate threads using `asyncio.to_thread` to prevent blocking the server's main event loop.
    *   Resilience for GCP API calls is enhanced through automatic retries using the `tenacity` library.
4.  **BQ Job Management (`job_store.py`):**
    *   The `FirestoreBqJobStore` class encapsulates all interactions with Google Cloud Firestore (specifically, Firestore in Datastore mode).
    *   It provides methods to `add` (create), `get` (retrieve), `update`, and `query` BigQuery job status records. Each job is stored as a document in Firestore, using its `job_id` as the document ID, ensuring job state persistence and recoverability.

## Prerequisites

Ensure the following prerequisites are met before setting up and running `mcp.agent`:

1.  **Python:** Version 3.9 or higher.
2.  **GCP Project:**
    *   A Google Cloud Platform project with billing enabled.
    *   **Enabled APIs:** Ensure the following APIs are enabled in your GCP project:
        *   Cloud Storage API
        *   BigQuery API
        *   **Firestore API** (and ensure a Firestore database has been created, preferably in Datastore mode, within your project).
        *   **Secret Manager API** (only if you plan to use Secret Manager for storing the `mcp.agent` API key).
3.  **Authentication (ADC):**
    *   The environment where `mcp-agent` will run must have Application Default Credentials (ADC) configured. This can typically be achieved by running `gcloud auth application-default login` or by setting the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to point to a service account key file.
4.  **IAM Permissions:** The service account or user credentials utilized by `mcp.agent` (via ADC) require the following IAM roles (or equivalent custom permissions) in your GCP project:
    *   **GCS Access:** `roles/storage.objectViewer` (to read objects), `roles/storage.objectCreator` (to write objects). For broader access, `roles/storage.admin` can be used but grant permissions judiciously.
    *   **BigQuery Access:** `roles/bigquery.jobUser` (to run jobs), `roles/bigquery.dataViewer` (to read data). `roles/bigquery.user` is a common alternative.
    *   **Firestore Access:** `roles/datastore.user` (to read and write job state).
    *   **Secret Manager Access:** `roles/secretmanager.secretAccessor` (if using Secret Manager for the API key).
    *   **Service Account Token Creation:** `roles/iam.serviceAccountTokenCreator` (this permission must be granted *on the service account itself* if that service account is used for generating GCS Signed URLs).
5.  **MCP Client:** An MCP client library or compatible tool (such as the Agent Development Kit - ADK) to interact with the `mcp.agent` server.
6.  **(Optional) ADK Setup:** If you plan to use the Agent Development Kit (ADK) as your client.

## Installation

1.  **Install Python Dependencies:**
    Open your terminal and run:
    ```bash
    pip install model-context-protocol google-cloud-storage google-cloud-bigquery python-dotenv python-json-logger google-cloud-secret-manager tenacity google-cloud-firestore
    ```
2.  **Install `mcp.agent`:**
    If installing from the source code directory:
    ```bash
    cd path/to/mcp_agent_source
    pip install .
    ```

## Usage

### 1. Running the `mcp.agent` Server

The command structure for starting the server remains consistent, but remember its behavior is now entirely stateless regarding user context (like default GCS buckets or BQ datasets).

**Example (SSE transport on port 8080, API key authentication required):**
```bash
mcp-agent --tools storage,bigquery --port 8080 --require-api-key
```
*If you use the `--require-api-key` flag, ensure that either `MCP_AGENT_API_KEY_SECRET_NAME` (for Google Secret Manager) or `MCP_AGENT_API_KEY` (for a direct key value) is correctly set in your server's environment or within an `.env` file.*

➡️ *Make a note of the connection details (e.g., port, whether an API key is needed) from the server's startup output. You'll need this information to configure your MCP client.*

### 2. Connecting Clients

Client connection setup follows standard MCP procedures. The key difference with `mcp.agent` v1.0.0 lies in the *interaction logic after connection*, due to the server's stateless design.

### 3. Agent Interaction Logic (v1.0.0 - Stateless Pattern)

When developing your agent (e.g., an LLM-based system or other automated client) to use tools provided by `mcp.agent`, adhere to these guidelines:

*   ✅ **Always Check Status:** Parse every JSON response from a tool call and inspect the `"status"` field to determine success or failure.
*   🔑 **Provide Full Identifiers:** For any tool that operates on specific GCP resources (which includes most GCS and BQ tools), your client **must** include all necessary identifiers, such as `bucket_name`, `project_id`, and `dataset_id`, in the arguments of each tool call. The server does not remember these details from previous calls.
*   🔗 **Working with GCS Signed URLs:**
    *   Call `gcs_get_read_signed_url` to obtain a temporary URL for downloading an object directly from GCS.
    *   Call `gcs_get_write_signed_url` to obtain a temporary URL for uploading an object directly to GCS.
    *   Your client application (or the end-user) must then perform the actual HTTP GET (for downloads) or PUT (for uploads) operation using the provided `"signed_url"`.
*   ⏳ **Asynchronous BigQuery Polling Workflow:**
    1.  **Submit Query:** Call `bq_submit_query` with your SQL statement. Securely store the `job_id` and `location` returned in the response; these are crucial for tracking the job.
    2.  **Poll for Status:** Periodically call `bq_get_job_status`, providing the stored `job_id` and `location`. Examine the `"state"` field in the response (e.g., `RUNNING`, `DONE`).
    3.  **Process Results (on Success):** If the `"state"` is `"DONE"` and the overall tool call `"status"` is `"success"`:
        *   The first page of query results will be available in the `"rows"` and `"schema"` fields of the `bq_get_job_status` response itself. Process this data.
        *   Check if a `"next_page_token"` is present in the response.
    4.  **Fetch Subsequent Pages:** If a `"next_page_token"` was returned, call `bq_get_query_results` with the `job_id`, `location`, and the `page_token` to retrieve the next page of results. Repeat this step until no `next_page_token` is returned.
    5.  **Handle Errors:** If the query `"state"` becomes `"ERROR"`, or if any tool call returns a failure `"status"`, use the `"message"` field from the JSON response for error diagnosis and reporting.
*   📢 **Report Errors Clearly:** Ensure that any error messages obtained from the `"message"` field in tool responses are clearly presented to the end-user or logged appropriately by the calling application.

## Tool Reference (v1.0.0 Changes)

Key changes to the available tools and their usage in `mcp.agent` v1.0.0:

*   **REMOVED Tools:** The following context-setting tools have been removed to enforce stateless operation:
    *   `gcs_set_context_bucket`
    *   `gcs_clear_context_bucket`
    *   `bq_set_context_dataset`
    *   `bq_clear_context_dataset`
*   **REQUIRED ARGUMENTS:**
    Specific identifiers are now mandatory for most GCS and BQ tools that interact with particular cloud resources.
    *   **For GCS tools:** `bucket_name` is generally required when operating on objects within a bucket.
    *   **For BQ tools:** `project_id` and `dataset_id` are generally required. `table_id` is needed for table-specific operations.

    **Affected GCS Tools (Examples):**
    *   `gcs_list_objects` (requires `bucket_name`)
    *   `gcs_get_read_signed_url` (requires `bucket_name` and `object_name`)
    *   `gcs_get_write_signed_url` (requires `bucket_name` and `object_name`)
    *   `gcs_write_string_object` (requires `bucket_name` and `object_name`)
    *   *Note: `gcs_list_buckets` does not require `bucket_name` but operates at the project level.*

    **Affected BQ Tools (Examples):**
    *   `bq_list_datasets` (requires `project_id`)
    *   `bq_list_tables` (requires `project_id` and `dataset_id`)
    *   `bq_get_table_schema` (requires `project_id`, `dataset_id`, and `table_id`)
    *   `bq_submit_query` (requires `project_id` for billing/quotas, `dataset_id` can be optional if tables are fully qualified in query)
    *   `bq_get_job_status` (requires `job_id` and `location` which implies project)
    *   `bq_get_query_results` (requires `job_id` and `location` which implies project)

*(For the most accurate and complete tool schemas, always refer to the definitions in the source code, primarily within `gcp_tools/__init__.py`.)*

## ⚠️ Limitations (v1.0.0 Highlights)

Please be aware of the following limitations in this version of `mcp.agent`:

*   **Stateless Context Burden on Client:** While the stateless server design enhances scalability, it shifts the responsibility of managing context (such as current bucket or dataset names) entirely to the client. Clients must send all necessary identifiers with each relevant tool call.
*   **Increased Client-Side Complexity:** Implementing features like asynchronous BigQuery job polling and handling GCS Signed URL redirects requires more sophisticated logic on the client-side.
*   **Firestore Dependency & Cost:** The tool now depends on Google Cloud Firestore for persisting BigQuery job states. This necessitates Firestore setup in your GCP project, appropriate IAM permissions, and may incur operational costs, especially with a high volume of BigQuery jobs.
*   **Narrow Service Scope:** Current functionality is focused on selected operations for Google Cloud Storage and BigQuery. Other GCP services are not supported.
*   **Basic Cloud Functionality:** The implemented tools cover common use cases but omit many advanced features and configuration options available within GCS and BigQuery.
*   **Application Default Credentials (ADC) Only:** Authentication is solely based on ADC. The tool does not support user impersonation or other GCP authentication mechanisms.
*   **Scalability Considerations for Production:**
    *   While inherently more scalable due to statelessness, a production deployment would necessitate appropriate infrastructure, including load balancing and potentially container orchestration.
    *   The server-side background poller for BigQuery jobs might become a performance bottleneck at extremely high job throughput. For such scenarios, consider alternative architectures like using Google Cloud Tasks or Cloud Functions triggered by BQ job completion events.
*   **Minimal Security Hardening:** The security model relies on the inherent security of ADC, network-level security, transport layer security (e.g., HTTPS if using SSE over a reverse proxy), and an optional basic API key for SSE. The codebase has not undergone comprehensive security audits or hardening for production environments.

**Critical Note:** `mcp.agent` v1.0.0 is a proof-of-concept. It is crucial to consult the detailed `Limitations.md` document (which should be updated for v1.0.0 specifics) for a thorough understanding of all constraints and potential risks before considering its use in sensitive or production systems.

## Contributing

This project is currently a proof-of-concept. While formal contributions are not being solicited at this stage, feedback and suggestions are welcome via issues on the project's repository (if applicable).

## License

(Example: Apache License 2.0 - Please replace with your chosen license)
