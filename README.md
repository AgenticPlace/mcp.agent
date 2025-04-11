# `mcp.agent`: Simplified & Context-Aware GCP Integration for MCP Agents

**(Disclaimer: This is documentation for a hypothetical tool, `mcp.agent`. The codebase provided previously is a functional proof-of-concept. It requires comprehensive testing, security hardening, and feature refinement for any production use.)**

`mcp.agent` is a command-line tool designed to significantly ease the integration of common Google Cloud services – specifically **Google Cloud Storage (GCS)** and **BigQuery (BQ)** – into applications using the **Model Context Protocol (MCP)**.

It achieves this by automating the creation and management of a specialized MCP server. This server exposes GCS and BQ functionalities as standard MCP tools, complete with **connection-specific context management** (remembering the current bucket or dataset), enabling more natural and efficient interactions for any MCP-compliant client, including agents built with the Agent Development Kit (ADK).

## The Problem Solved

Integrating cloud services into AI agents or applications often involves repetitive and complex setup:

*   Implementing an MCP server from scratch.
*   Writing wrappers around GCP SDK calls to expose them as tools.
*   Handling GCP authentication securely (without hardcoding credentials).
*   Managing conversational context (e.g., "Which bucket are we working in?").

`mcp.agent` abstracts away much of this complexity for common GCS and BQ workflows, letting you focus on your application's core logic.

## Core Features

*   🚀 **Automated Server Launch:** Start a dedicated GCP MCP server with a single command.
*   🛠️ **Focused GCP Toolset:** Pre-built, context-aware tools for common GCS (buckets, objects) and BigQuery (datasets, tables, queries) operations.
*   🧠 **Context Management:** Remembers the active GCS bucket and BQ project/dataset *per client connection*, minimizing repetitive parameters.
*   🧩 **Standard MCP Interface:** Fully compatible with any MCP client via standard `list_tools` and `call_tool` methods.
*   🔒 **Server-Side Authentication:** Securely uses Application Default Credentials (ADC) detected in the server's environment.
*   🌐 **Flexible Transports:** Supports `stdio` (local development) and `sse` (network access via HTTP Server-Sent Events).
*   📄 **Basic Pagination:** Handles paginated results for GCS object listing and BigQuery queries.

## How it Works: Technical Overview

`mcp.agent` orchestrates several components:

1.  **Command-Line Interface (`cli.py`):**
    *   Uses `argparse` to process user arguments (`--tools`, `--port`, `--host`, etc.).
    *   Validates input and sets up logging.
    *   Selects the appropriate server transport (`stdio` or `sse`).
2.  **MCP Server Core (`server.py`):**
    *   Instantiates the `McpAgentServer` class.
    *   Initializes a `ConnectionContextManager` (`context.py`) to track state per connection ID.
    *   Based on the `--tools` argument, loads the relevant MCP tool schemas and implementation functions from `gcp_tools`.
    *   Leverages the `model-context-protocol` library to create the underlying MCP server (`mcp_server.Server`).
    *   Registers handlers for core MCP methods:
        *   `list_tools`: Returns schemas of enabled GCS/BQ tools.
        *   `call_tool`: Maps tool names to implementation functions, passing arguments and context.
        *   `on_disconnect`: Cleans up context for the disconnected client.
    *   Launches the server using the chosen transport (`stdio_server` or `sse_server`).
3.  **GCP Tool Implementations (`gcp_tools/*.py`):**
    *   Functions like `gcs_list_objects` or `bq_query` encapsulate GCP interactions.
    *   They initialize `google-cloud-storage` and `google-cloud-bigquery` clients lazily (reusing them per process) and rely on **ADC** for authentication.
    *   Tool functions check input arguments; if key identifiers (like `bucket_name`) are missing, they query the `ConnectionContextManager` for the value associated with the current `conn_id`.
    *   **Crucially**, blocking GCP SDK calls (like network I/O) are executed in separate threads using `asyncio.to_thread` to prevent blocking the server's main asynchronous event loop.
    *   Responses (including errors) are consistently formatted into JSON strings (`{"status": "...", "message": "...", "data": ...}`) using helpers from `utils.py` and returned within standard `mcp_types.TextContent`.
4.  **Context Management (`context.py`):**
    *   The `ConnectionContextManager` uses a thread-safe (`asyncio.Lock`) dictionary to store context data (`gcs_bucket`, `bq_project`, `bq_dataset`) keyed by the unique MCP connection ID. This ensures context isolation between different connected clients. Context is purely in-memory and lost on server restart or client disconnect.

## Prerequisites

1.  **Python:** Version 3.9 or higher.
2.  **Google Cloud Project:** An active GCP project with billing enabled.
3.  **Enabled APIs:** Ensure the following APIs are enabled in your GCP project console:
    *   `Cloud Storage API`
    *   `BigQuery API`
4.  **Authentication (ADC):** The environment running `mcp-agent` needs GCP credentials. For local development, the easiest way is:
    *   Install `gcloud` CLI (Google Cloud SDK).
    *   Run: `gcloud auth application-default login`
    *(For deployments, configure the service account running `mcp.agent` with appropriate IAM roles).*
5.  **MCP Client Library:** Required if connecting programmatically (e.g., `pip install model-context-protocol`).
6.  **ADK (Optional):** If connecting an ADK agent, follow the ADK setup guide.

## Installation

1.  **Python Dependencies:**
    ```bash
    pip install model-context-protocol google-cloud-storage google-cloud-bigquery
    ```
2.  **Install `mcp.agent` Tool:**
    *(Assuming you have the source code from the previous step)*
    ```bash
    # Navigate to the project directory (containing pyproject.toml)
    cd path/to/mcp_agent_source

    # Install (standard)
    pip install .

    # Or install in editable mode (for development)
    pip install -e .
    ```

## Usage

### 1. Running the `mcp.agent` Server

Execute `mcp-agent` from your terminal. Remember to keep this process running while clients need to connect.

```bash
mcp-agent --tools <storage|bigquery|storage,bigquery> --port <stdio|PORT_NUMBER> [options]
Use code with caution.
Markdown
Common Options:
Argument	Required	Description	Example
--tools	Yes	Comma-separated services to enable (storage, bigquery).	--tools storage,bigquery
--port	Yes	Connection mode: stdio or SSE port number.	--port stdio, --port 8080
--host	No	(SSE only) Host IP to bind (default 127.0.0.1). Use 0.0.0.0 for network access.	--host 0.0.0.0
--require-api-key	No	(SSE only) Require Authorization: Bearer <key> header.	--require-api-key MySecretVal
--debug	No	Enable verbose debug logging.	--debug
Example Scenarios:
# Scenario 1: Local GCS tools via stdio
mcp-agent --tools storage --port stdio

# Scenario 2: GCS & BQ tools via SSE on port 9000, network accessible
mcp-agent --tools storage,bigquery --port 9000 --host 0.0.0.0

# Scenario 3: SSE with API key authentication
mcp-agent --tools storage --port 8080 --require-api-key superSecretKey123!
Use code with caution.
Bash
➡️ Important: Note the connection details (Command: for stdio, URL: and Headers: for SSE) printed by the server upon startup. You'll need these for your client.
2. Connecting Clients
A) Connecting ADK Agents
Use ADK's MCPToolset and the connection parameters from the server output.
# Example ADK Agent Connection
import asyncio
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters, SseServerParams

async def get_gcp_tools_async():
    """Connects to the mcp.agent managed GCP server."""
    print("Connecting to mcp.agent...")

    # --- STDIO Example ---
    # *** REPLACE with actual command/args from `mcp-agent --port stdio` output ***
    stdio_command = 'python'
    stdio_args = ["-m", "mcp_agent.cli", "--tools", "storage,bigquery", "--port", "stdio"]

    tools, exit_stack = await MCPToolset.from_server(
        connection_params=StdioServerParameters(command=stdio_command, args=stdio_args)
    )

    # --- SSE Example ---
    # *** REPLACE with actual URL/headers from `mcp-agent --port <num>` output ***
    # sse_url = "http://localhost:8080/mcp"
    # sse_headers = None # Or {"Authorization": "Bearer <key>"}
    #
    # tools, exit_stack = await MCPToolset.from_server(
    #     connection_params=SseServerParams(url=sse_url, headers=sse_headers)
    # )

    print(f"Connected. Fetched {len(tools)} tools.")
    # **IMPORTANT:** The exit_stack MUST be managed and closed later
    return tools, exit_stack

# --- Agent Definition (Instructions are key!) ---
async def get_agent_async():
    tools, exit_stack = await get_gcp_tools_async()
    agent_instructions = """
    You are a GCP assistant using MCP tools. Key points:
    - Use 'gcs_set_context_bucket' or 'bq_set_context_dataset' to set defaults when the user indicates focus.
    - After context is successfully set, omit bucket/project/dataset args in subsequent calls unless the user specifies a different one.
    - *Always* check the 'status' field in the JSON response. If 'error', report the 'message' clearly.
    - If 'next_page_token' exists and is not null in a response, inform the user there are more results and ask if they want the next page. If yes, call the same tool again passing the token in the 'page_token' argument.
    - If context isn't set and an operation needs it (e.g., you get a 'context not set' error), ask the user to specify the bucket/dataset or suggest listing available resources.
    """ # Add more detail specific to your agent's persona and capabilities
    root_agent = LlmAgent( model='gemini-1.5-flash-latest', name='gcp_mcp_assistant', instruction=agent_instructions, tools=tools )
    return root_agent, exit_stack

# --- Main Execution ---
async def async_main():
    # ... setup ADK Runner, SessionService etc. ...
    root_agent, exit_stack = await get_agent_async()
    # ... run the agent using runner.run_async(...) ...

    # **CRUCIAL CLEANUP: Ensure connection is closed**
    print("Closing MCP server connection...")
    if exit_stack: # Ensure exit_stack is not None before closing
      await exit_stack.aclose()
    print("Cleanup complete.")

if __name__ == '__main__':
    try:
        asyncio.run(async_main())
    except Exception as e:
        print(f"An error occurred: {e}")
Use code with caution.
Python
B) Connecting Generic MCP Clients (Python Example)
# Example generic client script
import asyncio
import json # Needed to parse response content
from mcp import client as mcp_client
from mcp import types as mcp_types

async def interact_with_gcp_server_stdio():
    # *** REPLACE with actual command/args from server output ***
    command = "python"
    args = ["-m", "mcp_agent.cli", "--tools", "storage", "--port", "stdio"]
    print(f"Connecting via stdio...")
    # Use context manager for cleanup
    async with mcp_client.stdio_client(command, args) as client:
        await perform_mcp_interaction(client)

async def interact_with_gcp_server_sse():
    # *** REPLACE with actual URL from server output ***
    sse_url = "http://localhost:8080/mcp"
    # *** Add headers if --require-api-key was used ***
    headers = None # e.g., {"Authorization": "Bearer mysecretkey123"}
    print(f"Connecting via SSE to {sse_url}...")
    # Use context manager for cleanup
    async with mcp_client.sse_client(sse_url, headers=headers) as client:
        await perform_mcp_interaction(client)

async def perform_mcp_interaction(client):
    """Demonstrates calling tools and parsing responses."""
    print("Connected. Listing tools...")
    available_tools = await client.list_tools()
    print("Available Tools:", [t.name for t in available_tools])

    try:
        # *** REPLACE with your actual bucket name ***
        target_bucket = 'your-real-gcs-bucket-name'

        print(f"\nAttempting to set GCS context to: {target_bucket}")
        result_list = await client.call_tool(
            name='gcs_set_context_bucket',
            arguments={'bucket_name': target_bucket}
        )

        # **IMPORTANT**: Process the response (expecting JSON inside TextContent)
        response_status = "error"
        response_data = {}
        if result_list and isinstance(result_list[0], mcp_types.TextContent):
            try:
                response_data = json.loads(result_list[0].text)
                response_status = response_data.get("status", "error").lower()
                print(f"Context set response JSON: {response_data}")
            except json.JSONDecodeError:
                print(f"Context set raw response (not JSON): {result_list[0].text}")
        else:
             print(f"Unexpected response format for context set: {result_list}")


        if response_status == "success":
            print("\nAttempting to list objects in context bucket...")
            list_result_list = await client.call_tool(
                name='gcs_list_objects',
                arguments={} # Use context
            )
            print("Raw list result:", list_result_list)
            # **IMPORTANT**: Process list_result_list similarly
            if list_result_list and isinstance(list_result_list[0], mcp_types.TextContent):
                try:
                    list_data = json.loads(list_result_list[0].text)
                    list_status = list_data.get("status", "error").lower()
                    print(f"List objects response JSON: {list_data}")
                    if list_status == "success":
                        items = list_data.get("data", {}).get("items", [])
                        next_page_token = list_data.get("data", {}).get("next_page_token")
                        print(f"Found {len(items)} items on this page.")
                        if next_page_token:
                            print(f"More results available (next_page_token: {next_page_token[:10]}...)")
                        # Further process items...
                    else:
                         print(f"Error listing objects: {list_data.get('message')}")
                except json.JSONDecodeError:
                    print(f"List result raw response (not JSON): {list_result_list[0].text}")
            else:
                print(f"Unexpected response format for list objects: {list_result_list}")
        else:
            print(f"Failed to set context (status: {response_status}), cannot list objects.")
            # Handle the error based on response_data['message']

    except Exception as e:
        print(f"An unexpected error occurred during interaction: {e}")

if __name__ == "__main__":
    # Choose one based on how the server was started
    asyncio.run(interact_with_gcp_server_stdio())
    # asyncio.run(interact_with_gcp_server_sse())
Use code with caution.
Python
3. Agent Interaction Logic (Key Patterns)
Instruct your agent (especially LLMs) to:
✅ Check Status: Always examine the "status" field ("success" or "error") in the JSON response from any mcp.agent tool call.
🧠 Use Context: Use gcs_set_context_bucket/bq_set_context_dataset when appropriate. After context is successfully set, omit the corresponding ID arguments (bucket_name, project_id, dataset_id) in subsequent calls to leverage the default.
➡️ Handle Pagination: If a response includes a non-null "next_page_token" in its data field, inform the user there are more results and ask if they want the next page. If yes, call the same tool again, adding the received token as the page_token argument.
❓ Clarify: If context isn't set and an operation needs it (indicated by an error response), ask the user to specify the resource or suggest listing available resources (e.g., gcs_list_buckets).
📢 Report Errors: Clearly communicate error messages received from the tool (response_data['message']) back to the user.
Tool Reference
The server exposes tools based on the --tools flag. All tools return a list containing one mcp_types.TextContent object, which holds a JSON string. Parse this JSON and check the status field.
GCS Tools (--tools storage):
gcs_list_buckets()
gcs_set_context_bucket(bucket_name)
gcs_clear_context_bucket()
gcs_list_objects([bucket_name], [prefix], [page_token], [max_results])
gcs_read_object(object_path, [bucket_name])
gcs_write_object(object_path, content, [bucket_name])
BQ Tools (--tools bigquery):
bq_set_context_dataset(project_id, dataset_id)
bq_clear_context_dataset()
bq_list_datasets([project_id])
bq_list_tables([project_id], [dataset_id])
bq_get_table_schema(table_id, [project_id], [dataset_id])
bq_query(query, [project_id], [dataset_id], [max_results], [page_token])
(Refer to the mcp_agent/gcp_tools/__init__.py file in the source code for detailed argument definitions).
⚠️ Limitations
This tool is a functional proof-of-concept and has significant limitations:
Narrow Scope: Only GCS and BigQuery are supported.
Basic Functionality: Omits many advanced GCP SDK features and parameters.
ADC Auth Only: No support for user impersonation or other auth flows.
In-Memory Context: Context is lost on disconnect or server restart.
Scalability: Designed primarily for local use or low-concurrency scenarios. Scaling requires external infrastructure.
Synchronous Operations: Long-running BQ queries or large GCS downloads can cause timeouts or high memory usage.
Minimal Security: Basic API key for SSE; relies heavily on network security and ADC permissions.
Critical: Please consult the detailed Limitations.md document (provided alongside the source code) for a comprehensive understanding of the constraints before using mcp.agent for anything beyond basic experimentation.
License
(Example: Apache License 2.0 - Replace with your actual license)
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0
Use code with caution.
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
Use code with caution.
