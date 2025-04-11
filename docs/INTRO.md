# Welcome to mcp.agent! (v1.0.0)

`mcp.agent` makes it easier to let your AI agents or applications talk to Google Cloud Storage (GCS) and BigQuery (BQ) using the Model Context Protocol (MCP).

Think of it as a ready-made bridge or adapter. You run the `mcp-agent` server, and your MCP client (like one built with ADK) can connect to it and start using tools like `gcs_list_objects` or `bq_submit_query` without needing complex GCP setup directly in the client.

**Version 1.0.0 Highlights:**

*   ✅ **Stateless:** Easier to scale and deploy (clients provide bucket/dataset IDs).
*   💾 **Persistent BQ Jobs:** Tracks long-running BigQuery queries using Firestore.
*   🔗 **Scalable GCS Files:** Uses efficient GCS Signed URLs for large file downloads/uploads.
*   ⏳ **Async BQ:** Submits BQ queries without blocking the server.
*   🔒 **Secure Auth:** Uses standard Google Cloud authentication (ADC) on the server.
*   🔑 **Env Config:** Supports `.env` files and Google Secret Manager for API keys.

## What can it do?

`mcp.agent` provides MCP tools for common tasks:

*   **Google Cloud Storage (GCS):**
    *   List your buckets.
    *   List objects (files/directories) within a bucket (with pagination).
    *   Get secure, temporary links (Signed URLs) for clients to directly download large files from GCS.
    *   Get secure, temporary links (Signed URLs) for clients to directly upload large files to GCS.
    *   Write *small* text snippets directly to GCS objects.
*   **BigQuery (BQ):**
    *   List datasets in your project.
    *   List tables within a dataset.
    *   Get the schema (column names/types) of a table.
    *   Submit SQL queries asynchronously (doesn't block).
    *   Check the status of submitted queries.
    *   Fetch query results (with pagination) once completed.

## Who is this for?

*   Developers building AI agents (e.g., using ADK) who need to interact with GCS or BigQuery.
*   Developers creating applications that communicate with external tools via the Model Context Protocol.
*   Anyone looking to simplify common GCP interactions within an MCP ecosystem.

## How to Get Started

Here's the quick path to trying out `mcp.agent`:

**1. Prerequisites:**

*   **Python 3.9+:** Make sure you have a compatible Python version.
*   **GCP Project:** You need a Google Cloud project with billing enabled.
*   **Enable APIs:** Go to your GCP Console and enable:
    *   `Cloud Storage API`
    *   `BigQuery API`
    *   `Firestore API` (and create a Firestore database in **Datastore mode**)
    *   `Secret Manager API` (if using for API key)
*   **Authenticate Locally (ADC):** Install `gcloud` (Google Cloud SDK) and run:
    ```bash
    gcloud auth application-default login
    gcloud config set project YOUR_PROJECT_ID
    ```
*   **Grant IAM Roles:** The identity you authenticated with (your user or a service account if running in GCP) needs permissions. Key roles include:
    *   `Storage Object Viewer/Creator` (for GCS)
    *   `BigQuery Job User`, `BigQuery Data Viewer` (for BQ)
    *   `Cloud Datastore User` (for Firestore BQ job state)
    *   `Secret Manager Secret Accessor` (if using Secret Manager)
    *   `Service Account Token Creator` (*on the identity itself*, for Signed URLs) - Search IAM for your email/SA and add this role.

**2. Installation:**

*   Clone the source code repository for `mcp.agent`.
*   Navigate to the project directory.
*   Install dependencies (including `mcp.agent` itself):
    ```bash
    pip install .
    # Or for development: pip install -e .
    ```

**3. Configuration (Optional API Key):**

*   If you want to secure the SSE server with a simple API key:
    *   Create a file named `.env` in the project directory.
    *   Add the line: `MCP_AGENT_API_KEY=your_super_secret_key` (replace with a strong key).
    *   *(Alternatively, set the `MCP_AGENT_API_KEY_SECRET_NAME` variable to fetch from Secret Manager - see README.md)*.
    *   **Add `.env` to your `.gitignore`!**

**4. Run the Server:**

*   Open your terminal in the project directory.
*   Choose your mode (`stdio` or `sse`) and enabled tools.

    *   **Example (stdio, GCS & BQ):**
        ```bash
        mcp-agent --tools storage,bigquery --port stdio
        ```
    *   **Example (SSE on 8080, GCS only, require API key from `.env`):**
        ```bash
        mcp-agent --tools storage --port 8080 --require-api-key
        ```
*   Note the connection details printed by the server. Keep this terminal running.

**5. Connect Your Client:**

*   Use your preferred MCP client library (like ADK's `MCPToolset`).
*   Provide the connection details (command/args for stdio, URL/headers for SSE) obtained from the server output.

**6. Use the Tools:**

*   Call `list_tools` to see available actions.
*   Use `call_tool` with the required arguments (remember `bucket_name`, `project_id`, `dataset_id` are now often mandatory!).
*   Follow the specific workflows for GCS Signed URLs and the BQ async pattern (submit -> poll status -> get results) as detailed in `USAGE.md`.
*   Always parse the JSON response and check the `status` field.

## Next Steps

*   **Usage Details:** See `USAGE.md` for detailed command examples and client interaction patterns.
*   **Technical Dive:** Explore `TECHNICAL.md` for architecture and implementation specifics.
*   **Limitations:** Understand the constraints and PoC nature by reading `Limitations.md`.
*   **Deployment:** Review `PRODUCTION_DEPLOYMENT.md` (generated previously, outlining production considerations) before attempting to deploy outside local testing.

---

This `INTRO.md` aims to give a quick, friendly overview and guide users to the essential steps and further documentation.
