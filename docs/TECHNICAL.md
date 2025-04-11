# `mcp.agent` Technical Details (v1.0.0)

This document provides a deeper technical overview of the `mcp.agent` (v1.0.0) implementation, intended for developers contributing to, extending, or understanding the internal workings of the service. It complements the user-focused `README.md` and `USAGE.md`.

## Architecture Overview

`mcp.agent` acts as a specialized gateway between MCP clients and specific Google Cloud services (GCS, BigQuery).

```mermaid
graph LR
    Client[MCP Client (e.g., ADK Agent)] -- MCP (stdio/sse) --> Server(mcp.agent Process);
    Server -- GCP SDK --> GCS[Google Cloud Storage];
    Server -- GCP SDK --> BQ[Google BigQuery];
    Server -- GCP SDK --> FS[Firestore (for BQ Jobs)];
    Server -- GCP SDK --> SM[(Optional) Secret Manager];

    subgraph "mcp.agent Process"
        direction TB
        MCP_Handler[MCP Server Handler (server.py)];
        Tool_Router[Tool Router];
        GCS_Tools[GCS Tools (storage.py)];
        BQ_Tools[BQ Tools (bigquery.py)];
        BQ_Job_Store[BQ Job Store (job_store.py - Firestore)];
        BQ_Poller[BQ Background Poller];
        Utils[Utilities (utils.py)];
        GCP_Clients[GCP Clients (Lazy Init)];

        MCP_Handler --> Tool_Router;
        Tool_Router --> GCS_Tools;
        Tool_Router --> BQ_Tools;
        GCS_Tools --> GCP_Clients;
        BQ_Tools --> GCP_Clients;
        BQ_Tools --> BQ_Job_Store;
        BQ_Poller --> BQ_Job_Store;
        BQ_Poller --> GCP_Clients; # (Specifically BQ client for get_job)
        GCP_Clients -->|ADC| GCP_Auth[GCP Authentication];
        Utils --> GCP_Clients; # (For Secret Manager)

    end

    style Server fill:#f9f,stroke:#333,stroke-width:2px
Use code with caution.
Markdown
Key Characteristics (v1.0.0):
Stateless Context: The server does not maintain per-connection default buckets or datasets. Clients must provide necessary identifiers (bucket_name, project_id, dataset_id) in each tool call.
Externalized BQ Job State: Asynchronous BigQuery job status is tracked persistently in Google Cloud Firestore (Datastore mode).
Server-Side GCP Auth: Authentication relies exclusively on Application Default Credentials (ADC) detected in the server's environment.
Asynchronous Core: Built on asyncio. Blocking I/O operations (GCP SDK calls, file operations if added) are delegated to separate threads using asyncio.to_thread.
Retries: Transient GCP API errors are automatically retried using tenacity.
Signed URLs for GCS I/O: Large file transfers between the client and GCS occur directly using time-limited Signed URLs, bypassing the server for bulk data.
Project Structure
mcp_agent/
├── __init__.py         # Package marker, version
├── __main__.py         # Allows running with `python -m mcp_agent`
├── cli.py              # Command-line interface parsing and main entry point
├── server.py           # Core McpAgentServer class, MCP handling, BQ Poller task
├── job_store.py        # FirestoreBqJobStore class for managing BQ job state
├── utils.py            # Formatting helpers, GCP error handling, Secret Manager access, retry definitions
└── gcp_tools/          # Module for GCP service interactions
    ├── __init__.py     # Defines tool schemas, maps names to functions
    ├── common.py       # (Removed, retry logic moved to utils.py)
    ├── storage.py      # GCS tool implementations (Signed URLs, list, etc.)
    └── bigquery.py     # BQ tool implementations (async submit/status/results, list, etc.)
tests/                  # Unit and Integration tests
├── __init__.py
├── test_utils.py
└── gcp_tools/
    ├── __init__.py
    └── test_storage.py
    └── test_bigquery.py
pyproject.toml          # Project metadata and dependencies (including testing)
requirements.txt        # Runtime dependencies (alternative to pyproject.toml for some envs)
.env.sample             # Example environment variables template
Dockerfile              # Container build instructions
.dockerignore           # Files excluded from Docker build context
README.md               # User-facing overview
USAGE.md                # How to run and interact with the server
TECHNICAL.md            # This file
Limitations.md          # Known constraints
Use code with caution.
Key Dependencies
model-context-protocol: Core library for implementing the MCP server and client interactions.
google-cloud-storage: Official GCP client library for Cloud Storage.
google-cloud-bigquery: Official GCP client library for BigQuery.
google-cloud-firestore: Official GCP client library for Firestore (Datastore mode).
google-cloud-secret-manager: Official GCP client library for Secret Manager (optional API key).
tenacity: Robust general-purpose retry library used for GCP API calls.
python-dotenv: Loads environment variables from .env files for configuration.
python-json-logger: Formats log output as JSON for better observability.
asyncio: Python's built-in library for asynchronous programming, used extensively.
Core Components
1. CLI (cli.py)
Uses argparse to define and parse command-line arguments (--tools, --port, --host, --require-api-key, --debug).
Initializes structured JSON logging using python-json-logger, directing logs to stderr.
Calls load_dotenv() to load .env file variables.
Determines the SSE API key:
Checks MCP_AGENT_API_KEY_SECRET_NAME env var first. If set, calls utils.fetch_secret (which uses the Secret Manager client) to retrieve the key.
If secret name not set, checks MCP_AGENT_API_KEY env var directly.
Fails startup if --require-api-key is set but no key can be obtained.
Performs pre-flight initialization checks for required GCP clients (GCS, BQ, Firestore, Secret Manager) to fail fast on auth/config errors.
Selects and runs the appropriate server function (run_stdio_server or run_sse_server) based on the --port argument.
Handles KeyboardInterrupt (Ctrl+C) for basic shutdown trigger.
2. MCP Server (server.py)
McpAgentServer Class:
Initializes FirestoreBqJobStore.
Initializes the core mcp_server.Server.
Loads available tool schemas (GCS_TOOLS_SCHEMAS, BQ_TOOLS_SCHEMAS) based on enabled --tools.
Registers handlers:
list_tools: Returns the loaded schemas.
call_tool: The main request router. Validates tool existence/enablement, looks up the implementation function in ALL_TOOLS_MAP, injects bq_job_store if needed, calls the tool function, and returns the result (McpToolReturnType). Includes generic exception handling around tool calls.
on_disconnect: Cleans up relevant BQ jobs from the FirestoreBqJobStore associated with the disconnected conn_id.
run: Contains the main server loop (self.server.run) driven by the transport.
BQ Background Poller (_poll_bq_jobs, start_poller, stop_poller):
_poll_bq_jobs runs as a separate asyncio.Task.
Periodically queries Firestore (bq_job_store.get_pending_or_running_jobs) for jobs in PENDING/RUNNING state.
For each active job (respecting a minimum re-poll delay), it calls the BigQuery API (client.get_job via asyncio.to_thread and retry decorator) to get the current status.
Updates the job status back into Firestore (bq_job_store.update_job_status).
Handles NotFound errors during polling (removes job from Firestore).
Uses asyncio.Event (_shutdown_event) for graceful shutdown signal.
start_poller/stop_poller manage the lifecycle of this background task.
Transport Functions (run_stdio_server, run_sse_server):
Initialize McpAgentServer.
Start/stop the BQ poller task if bigquery tools are enabled.
Use context managers (stdio_server, sse_server) from the mcp library to establish transport.
Configure SSE authentication handler based on the resolved API key.
Call agent_server.run to start processing MCP messages.
Include basic error handling for transport setup (e.g., port in use).
3. GCP Tools (gcp_tools/)
Stateless Design: Functions do not rely on server-side connection context. Required identifiers (bucket_name, project_id, dataset_id) must be passed in the arguments dictionary. Input validation is performed for these required arguments and potentially for path/query formats.
Async Wrapper (asyncio.to_thread): All blocking calls to the Google Cloud client libraries are wrapped in asyncio.to_thread to avoid stalling the main event loop.
Retries (@retry_on_gcp_transient_error): Synchronous helper functions making the actual GCP calls are decorated with @retry_on_gcp_transient_error (defined in utils.py) to automatically retry specific transient errors (5xx, 429, DeadlineExceeded). Non-retryable errors (NotFound, Forbidden, BadRequest, InvalidArgument) are caught after retries fail in the main async tool function and formatted as errors.
GCS Specifics (storage.py):
Uses blob.generate_signed_url(version="v4", method="GET"|"PUT") for read/write operations, returning the URL to the client. Requires appropriate service account permissions (Service Account Token Creator role on the service account itself).
gcs_write_string_object remains for small uploads via the server, performing a size check first.
BQ Specifics (bigquery.py):
bq_submit_query: Calls client.query (non-blocking start), stores job info (job_id, location, conn_id, initial state) in Firestore via FirestoreBqJobStore.add_job.
bq_get_job_status: Reads the current state from Firestore (FirestoreBqJobStore.get_job). If state is DONE+Success, it then makes a call to client.list_rows (with retries, via helper) to fetch the first page of results and includes them in the success response.
bq_get_query_results: Makes a call to client.list_rows (with retries, via helper) using the provided page_token to fetch subsequent pages only. Assumes the job is already known to be DONE.
Helper _serialize_row converts BQ Row objects to JSON-serializable dicts.
4. BQ Job Store (job_store.py)
FirestoreBqJobStore Class:
Uses google.cloud.firestore.AsyncClient for non-blocking Firestore operations.
Client initialization is lazy (_get_db).
Uses job_id as the Firestore document ID within a dedicated collection (BQ_JOB_COLLECTION).
add_job: Uses doc_ref.set() to create/overwrite job documents.
get_job: Uses doc_ref.get() to retrieve job documents.
update_job_status: Uses doc_ref.update() for partial updates of status, error, and timestamps.
get_pending_or_running_jobs: Uses a Firestore where().limit().stream() query to fetch active jobs for the poller. Requires Firestore indexes on status and potentially last_check_time for efficient querying at scale.
remove_job, cleanup_old_jobs: Provide deletion mechanisms.
Applies @retry_on_gcp_transient_error to Firestore operations.
5. Utilities (utils.py)
Response Formatting: format_success, format_error, format_info create the standard JSON payload within a single TextContent. format_chunked_response is present but unused by default in v1.0.0.
Error Handling: handle_gcp_error maps common google.api_core.exceptions to user-friendly error messages.
Secret Manager: get_secret_manager_client (cached) and fetch_secret (uses retry-wrapped sync helper _access_secret_version_sync) provide secure API key retrieval.
Retry Definition: Defines the retry_on_gcp_transient_error decorator using tenacity.
Authentication (ADC)
The application exclusively uses Application Default Credentials (ADC). The Google Cloud client libraries automatically find credentials in a specific order (environment variables like GOOGLE_APPLICATION_CREDENTIALS, gcloud user credentials, GCE/Cloud Run/App Engine metadata server).
The Service Account resolved via ADC must have the correct IAM permissions for all required actions on GCS, BigQuery, Firestore, and potentially Secret Manager and itself (iam.serviceAccountTokenCreator for Signed URLs).
Configuration
Primary configuration is via command-line arguments.
Sensitive values (optional SSE API key) are loaded from environment variables, prioritized:
MCP_AGENT_API_KEY_SECRET_NAME (fetches from Secret Manager)
MCP_AGENT_API_KEY (plain text key)
Uses python-dotenv to load these environment variables from a .env file automatically.
Logging
Uses standard Python logging configured with python-json-logger.JsonFormatter.
Logs are written to stderr in JSON format.
Includes standard log fields plus custom context added via extra={...} in logging calls (e.g., conn_id, tool_name, job_id).
Containerization
Dockerfile builds a container image based on python:3.11-slim.
Installs dependencies using pip and pyproject.toml.
Creates and runs as a non-root user (appuser).
Copies application code.
Sets mcp-agent as the ENTRYPOINT.
.dockerignore excludes unnecessary files from the build context.
Testing
Uses pytest and pytest-asyncio.
Unit tests (tests/test_utils.py) verify utility functions.
Integration tests (tests/gcp_tools/test_*.py, tests/test_integration.py):
Mock GCP client libraries (unittest.mock.patch, custom mock classes).
Verify tool logic, context (removed in v1.0.0), job store interactions, and routing within the McpAgentServer.
Current test coverage is foundational and needs expansion.
Known Technical Debt / Future Improvements
BQ Poller Scalability: The single background poller task might become a bottleneck with thousands of concurrent jobs. Consider distributed polling using Cloud Tasks or Pub/Sub + Cloud Functions.
Firestore Indexing: Explicit Firestore indexes are likely needed for status and last_update_time fields in the mcp_agent_bq_jobs collection for efficient polling and cleanup queries at scale.
Comprehensive Testing: Increase unit and integration test coverage significantly, including more edge cases and error conditions. Implement end-to-end tests.
Advanced GCP Features: Add support for more specific parameters in GCS/BQ tools (e.g., encryption keys, detailed job config, query parameters).
True Streaming: Replace GCS Signed URLs with WebSockets/gRPC if direct server-mediated streaming is absolutely required (major architectural change).
Monitoring Integration: Add explicit metric reporting (e.g., OpenTelemetry) for better observability beyond logs.
Advanced Security: Implement mTLS or OAuth for client authentication instead of relying solely on API keys or IAP. More granular input validation.
Use code with caution.
49.8s
