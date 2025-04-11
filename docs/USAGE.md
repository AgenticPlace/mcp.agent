# Using mcp.agent (v1.0.0)

This guide provides practical instructions on how to run the `mcp-agent` server and how clients can interact with the GCP tools it exposes.

**Assumptions:** You have reviewed the main `README.md` for project overview, features, and core concepts.

## Prerequisites

1.  **Python:** 3.9+
2.  **GCP Project:** Billing enabled, required APIs enabled (Cloud Storage, BigQuery, Firestore, Secret Manager if used).
3.  **GCP Authentication (ADC):** The environment running `mcp-agent` must have Application Default Credentials configured (e.g., `gcloud auth application-default login`).
4.  **IAM Roles:** The Service Account used by ADC needs appropriate roles (Storage access, BigQuery access, Firestore User, Secret Manager Secret Accessor, Service Account Token Creator). See `README.md` for details.
5.  **Installation:** `mcp.agent` and its dependencies (`google-cloud-*`, `python-dotenv`, etc.) must be installed (e.g., `pip install .` from source).

## 1. Running the `mcp-agent` Server

The primary way to use `mcp.agent` is via its command-line interface.

### Command Structure

```bash
mcp-agent --tools <services> --port <stdio|PORT> [options]
Use code with caution.
Markdown
Key Arguments
--tools <storage|bigquery|storage,bigquery>: Required. Specifies which GCP service tools to enable.
--port <stdio|PORT_NUMBER>: Required. Sets the communication mode.
stdio: Use standard input/output (for local testing, single client).
<PORT_NUMBER> (e.g., 8080): Use Server-Sent Events (SSE) over HTTP on the specified port.
--host <ip_address>: (SSE Only) IP address for the SSE server to listen on. Defaults to 127.0.0.1 (localhost). Use 0.0.0.0 to listen on all interfaces (required for access from other machines or containers).
--require-api-key: (SSE Only, Flag) If present, enables API key authentication. The server will require clients to send an Authorization: Bearer <key> header. The key itself MUST be provided via environment variables.
--debug: (Optional, Flag) Enables verbose debug logging to stderr.
Environment Variables for Configuration
mcp.agent uses python-dotenv to automatically load variables from a .env file in the current or parent directories.
MCP_AGENT_API_KEY_SECRET_NAME: (Optional)
Recommended for API Key Auth. If --require-api-key is used and this variable is set, mcp.agent will fetch the API key from the specified Google Secret Manager secret version name (e.g., projects/p/secrets/s/versions/latest).
The server's Service Account needs the roles/secretmanager.secretAccessor IAM role on this secret.
MCP_AGENT_API_KEY: (Optional)
If --require-api-key is used and MCP_AGENT_API_KEY_SECRET_NAME is not set, mcp.agent will use the value of this environment variable directly as the API key.
Less secure than using Secret Manager, suitable for local development with a .env file.
GCP Variables: Standard variables like GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_CLOUD_PROJECT are recognized by the underlying Google Cloud libraries for ADC configuration, but are not directly used by mcp.agent's code.
(See .env.sample for a template).
Example Commands
# 1. Run locally with GCS & BQ, using stdio
mcp-agent --tools storage,bigquery --port stdio

# 2. Run via SSE on port 8080, network accessible, BQ only
mcp-agent --tools bigquery --port 8080 --host 0.0.0.0

# 3. Run via SSE on port 9000, require API key loaded from environment/`.env`
# (Ensure MCP_AGENT_API_KEY_SECRET_NAME or MCP_AGENT_API_KEY is set first!)
mcp-agent --tools storage,bigquery --port 9000 --require-api-key --host 0.0.0.0
Use code with caution.
Bash
Server Output & Connection Details
When the server starts successfully, it will log information including how clients should connect:
For stdio: It will typically show the effective command and arguments needed for the client's StdioServerParameters.
For sse: It will show the URL (e.g., http://<host>:<port>/mcp) and any required Headers (like Authorization: Bearer ... if --require-api-key was used).
Stopping the Server
Press Ctrl+C in the terminal where mcp-agent is running.
2. Connecting a Client
Any MCP-compliant client can connect to the running mcp.agent server.
Connection Parameters: Use the details provided in the server's startup logs:
Stdio: Provide the command and arguments to your client's stdio connection logic (e.g., ADK's StdioServerParameters).
SSE: Provide the URL and any required headers (e.g., Authorization) to your client's SSE connection logic (e.g., ADK's SseServerParams).
ADK Example: Use MCPToolset.from_server(connection_params=...). Remember to manage and close the returned exit_stack.
Generic Client: Use libraries like model-context-protocol's client functions (stdio_client, sse_client).
3. Interacting with Tools (v1.0.0 Workflow)
This version requires specific interaction patterns due to its stateless nature and async handling.
A. General Interaction
List Tools: Call list_tools to discover available tools (will depend on the --tools flag used to start the server).
Call Tool: Use call_tool with the tool name and arguments.
Parse Response:
The response is typically a list containing one mcp_types.TextContent item.
The text field of this item contains a JSON string.
Always parse this JSON and check the "status" field ("success" or "error").
Use the "message" field for user feedback or error details.
Use the "data" field (if present) for successful results.
B. Stateless Context - Mandatory Identifiers!
Context tools (set_..., clear_...) are REMOVED. The server does not remember defaults per connection.
Requirement: Your client/agent MUST provide the necessary identifiers (bucket_name, project_id, dataset_id) as arguments in every call to tools that operate on specific resources (e.g., gcs_list_objects, bq_list_tables, gcs_get_read_signed_url). Check the tool schemas (gcp_tools/__init__.py) for required arguments.
C. GCS Large File I/O (Signed URLs)
Reading:
Call gcs_get_read_signed_url with bucket_name and object_path.
If status is "success", extract the "signed_url" from the data field.
The client application then performs an HTTP GET request directly to this signed_url using standard HTTP libraries (requests, aiohttp, browser fetch, curl, etc.) to download the file content. The mcp.agent server is not involved in the data transfer.
Writing:
Call gcs_get_write_signed_url with bucket_name and object_path (and optionally content_type).
If status is "success", extract the "signed_url" from the data field.
The client application then performs an HTTP PUT request directly to this signed_url, providing the file content in the request body.
Important: The client must set the Content-Type header in the PUT request, matching the content_type provided when generating the URL if one was specified.
Small Strings: For very small text content (< ~5MB), you can still use gcs_write_string_object which uploads the data through the server.
D. BigQuery Asynchronous Queries (Client Polling)
This requires a multi-step process managed by the client:
Submit: Call bq_submit_query with the query string (and optionally project_id, default_dataset_project_id, default_dataset_id).
If status is "success", store the "job_id" and "location" from the data field. The initial "state" will likely be "PENDING".
Poll Status: Periodically call bq_get_job_status with the stored job_id and location.
Check the "state" in the response data.
If "PENDING" or "RUNNING", wait (e.g., asyncio.sleep(3)) and repeat the status check.
If "ERROR", extract error details from "error_result" and stop.
If "DONE":
Check the overall call "status" first. If "error", report the "message" (e.g., error fetching results).
If "success", the first page of results ("rows", "schema") and the "next_page_token" (if any) are included directly in this status response. Process these rows. Proceed to step 3 if next_page_token exists.
Fetch Subsequent Pages (if needed):
If bq_get_job_status returned a "next_page_token" for the completed job, call bq_get_query_results with the job_id, location, and the received page_token.
Process the "rows" from this response.
Check the new "next_page_token" in the response. Repeat this step until "next_page_token" is null or empty.
E. Pagination (General)
For tools like gcs_list_objects and bq_get_query_results (after the first page):
Check the "next_page_token" field in the data section of a successful response.
If it's present and non-null, there are more results.
To get the next page, call the same tool again, passing the received token as the page_token argument.
Example Interaction Flow (Conceptual Agent)
USER: List objects in my bucket 'data-bucket-alpha'.

AGENT: (Calls `gcs_list_objects` with `bucket_name='data-bucket-alpha'`)
MCP_AGENT SERVER: (Returns JSON: status="success", data={ items: [...], next_page_token: "token123" })
AGENT: Okay, in 'data-bucket-alpha' I see [file1, file2, ...]. There are more results. Show next page?

USER: Yes

AGENT: (Calls `gcs_list_objects` with `bucket_name='data-bucket-alpha'`, `page_token='token123'`)
MCP_AGENT SERVER: (Returns JSON: status="success", data={ items: [...], next_page_token: null })
AGENT: The next items are [fileX, fileY, ...]. That's all.

USER: Run 'SELECT COUNT(*) FROM prod_dataset.users' in project 'my-prod-project'.

AGENT: (Calls `bq_submit_query` with `query='...'`, `project_id='my-prod-project'`, `default_dataset_project_id='my-prod-project'`, `default_dataset_id='prod_dataset'`)
MCP_AGENT SERVER: (Returns JSON: status="success", data={ job_id: "job_abc", location: "us-central1", state: "PENDING" })
AGENT: Okay, I submitted the query. Job ID is job_abc. I'll check the status.

AGENT: (Waits a few seconds...)
AGENT: (Calls `bq_get_job_status` with `job_id='job_abc'`, `location='us-central1'`)
MCP_AGENT SERVER: (Checks Firestore, sees poller updated state) -> (Returns JSON: status="success", data={ state: "DONE", schema: [...], rows: [{"f0_": 1500}], next_page_token: null })
AGENT: The query is complete! The count is 1500.

USER: Download the file 'reports/annual.pdf' from 'data-bucket-alpha'.

AGENT: (Calls `gcs_get_read_signed_url` with `bucket_name='data-bucket-alpha'`, `object_path='reports/annual.pdf'`)
MCP_AGENT SERVER: (Returns JSON: status="success", data={ signed_url: "https://...", method: "GET", ... })
AGENT: Okay, please use this secure link to download the file directly: https://... (Link expires in 5 minutes).
Use code with caution.
Important Notes
Statelessness: Remember to always provide bucket_name, project_id, dataset_id where required by tools.
Firestore: Ensure Firestore API is enabled and the service account has permissions (roles/datastore.user) if using BigQuery tools.
IAM Roles: Double-check the necessary IAM roles for the service account, especially roles/iam.serviceAccountTokenCreator for Signed URL generation.
