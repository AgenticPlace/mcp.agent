# `mcp.agent`: Supercharge Your MCP Agents with Google Cloud!

**(v1.0.0 - Beta)**

<p align="center">
  <!-- Consider adding a relevant visual or logo here -->
  <img src="placeholder_conceptual_graphic.png" alt="MCP Agent connecting Agent Brain to GCP Services" width="350"/>
</p>

**Stop Wrestling with Cloud APIs, Start Building Smarter Agents.**

## The Bottleneck: Bridging Agents to the Cloud is Hard

You're building intelligent agents using the **Model Context Protocol (MCP)** – a fantastic standard for providing context to LLMs. But when your agent needs the power of Google Cloud Storage (GCS) for files or BigQuery (BQ) for data analysis, things get complicated fast. You need to:

*   Build and maintain a compliant MCP server.
*   Securely authenticate to Google Cloud (without exposing keys!).
*   Translate complex SDK calls into simple MCP tools.
*   Efficiently handle large files or long-running queries without blocking your agent.
*   Manage conversational state related to cloud resources.

This infrastructure work slows you down and distracts from enhancing your agent's core intelligence.

## The Solution: `mcp.agent` - Your Plug-and-Play GCP<->MCP Server

`mcp.agent` eliminates the friction. It's a **pre-built, configurable MCP server** designed specifically for GCS and BQ.

Launch `mcp.agent` with a simple command, and instantly give **any MCP-compliant client** (like agents built with Google's ADK or the official `mcp` Python SDK) access to curated, production-ready GCP tools.

## Key Benefits: Why Choose `mcp.agent`?

*   🚀 **Instant GCP Integration:** Launch a fully functional GCS/BQ MCP server in minutes, not days.
*   🛠️ **Ready-Made Tools:** Access common cloud operations (list buckets/tables, read/write objects, query data) through standard MCP `call_tool`.
*   🔗 **Scalable File Transfers:** Handles large GCS files effortlessly using **secure, direct Signed URLs** – no server bottlenecks.
*   ⏳ **Non-Blocking BigQuery:** Submit complex BQ queries asynchronously. `mcp.agent` tracks job status persistently in **Firestore**, letting your client poll without waiting.
*   ✅ **Stateless & Scalable:** Designed for modern cloud deployments – easily run multiple instances behind a load balancer.
*   🔒 **Secure Foundation:** Leverages Google Cloud's robust **Application Default Credentials (ADC)** and supports API key management via **Secret Manager**.
*   🧩 **MCP Standard Compliant:** Works seamlessly with any standard MCP client or framework.
*   ☁️ **Focus on Your Agent:** Spend less time on cloud plumbing and more time on building unique agent capabilities.

## How It Works (The Simple Idea)

`mcp.agent` acts as a smart intermediary:

1.  You run the `mcp-agent` server process (e.g., in a container).
2.  It automatically authenticates to your GCP project using ADC.
3.  Your MCP Client connects to the `mcp.agent` server (via stdio or secure SSE/HTTPS).
4.  Your client calls standard MCP tools like `gcs_get_read_signed_url` or `bq_submit_query`.
5.  `mcp.agent` securely interacts with the corresponding GCP service (GCS, BQ, Firestore), using efficient patterns like Signed URLs and async job tracking.
6.  It returns standardized JSON responses (or URLs for direct GCS access) back to your client via MCP.

Essentially, it provides the **"Resources"** and **"Tools"** described in the MCP specification, specifically tailored for GCS and BQ, wrapped in a secure and scalable server.

## Example Use Cases: Unlock Cloud Power

*   **Document Analysis Agent:** Reads PDFs/text files from GCS using Signed URLs for processing by an LLM.
*   **Data Query Agent:** Takes natural language questions, translates them to SQL, submits them via `bq_submit_query`, polls status with `bq_get_job_status`, and presents results fetched via `bq_get_query_results`.
*   **Reporting Agent:** Generates reports and uploads them as large files directly to GCS using a write Signed URL obtained from `gcs_get_write_signed_url`.
*   **Cloud Assistant:** Helps users navigate their GCP resources by listing buckets (`gcs_list_buckets`), datasets (`bq_list_datasets`), or table schemas (`bq_get_table_schema`).

## Target Audience

*   **AI/LLM Application Developers:** Integrating GCP data/functionality into agentic workflows.
*   **ADK Users:** Need a simple way to give your ADK agent GCS/BQ access.
*   **MCP Adopters:** Looking for pre-built server implementations for common backend services.
*   **Platform Teams:** Providing standardized, secure access to GCP for internal agent builders.

## Get Started Quickly!

1.  **Check Prerequisites:** Ensure Python 3.9+, GCP setup (APIs enabled, ADC auth, IAM roles), and dependencies installed. (See `README.md`/`INTRO.md`)
2.  **Install:** `pip install .` from the source code.
3.  **Configure (Optional API Key):** Set `MCP_AGENT_API_KEY_SECRET_NAME` or `MCP_AGENT_API_KEY` in `.env` if using `--require-api-key` for SSE.
4.  **Run Server:** `mcp-agent --tools storage,bigquery --port 8080` (or other options). Note connection details.
5.  **Connect Client:** Point your MCP client (ADK, `mcp` SDK, etc.) to the server using the provided details.
6.  **Call Tools:** Start interacting! Remember clients need to handle Signed URLs and BQ polling. (See `USAGE.md`)

**Dive Deeper:**

*   **Quick Introduction:** `INTRO.md`
*   **Detailed Usage & Client Logic:** `USAGE.md`
*   **Technical Architecture:** `TECHNICAL.md`
*   **Understand Limitations:** `Limitations.md`

---

> **Current Status (v1.0.0): Beta / Proof-of-Concept**
>
> While incorporating robust patterns like Signed URLs and Firestore state, `mcp.agent` requires further production hardening (advanced security, monitoring, comprehensive testing). Review `PRODUCTION_DEPLOYMENT.md` guidance before deploying in critical environments. We welcome feedback and contributions!
