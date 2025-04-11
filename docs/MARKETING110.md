# `mcp.agent`: Your Scalable, Secure Bridge from MCP Agents to Google Cloud!

**(v1.1.0 - Beta: Improved Stability & Operations)**

<p align="center">
  <!-- Consider adding a relevant visual or logo here -->
  <img src="placeholder_conceptual_graphic_v11.png" alt="MCP Agent securely connecting Agent Brain to robust GCP Services" width="350"/>
</p>

**Stop Building Cloud Plumbing. Start Building Intelligent Agents.**

## The Agent-Cloud Gap

Your MCP agents need Google Cloud's power – GCS for files, BigQuery for data. But connecting them securely and scalably involves building complex infrastructure: MCP servers, GCP authentication, API wrappers, handling large files, managing async jobs... This is time-consuming boilerplate that slows you down.

## `mcp.agent`: The Instant GCP<->MCP Solution

`mcp.agent` provides a **production-aware, configurable MCP server** specifically for GCS and BQ. Launch it easily (e.g., as a container) and immediately empower any MCP client with robust, efficient cloud tools.

Version 1.1.0 builds on the scalable v1.0.0 foundation with enhanced operational readiness.

## Why `mcp.agent` v1.1.0?

*   🚀 **Rapid Deployment:** Get a GCS/BQ MCP server running in minutes.
*   🛠️ **Essential Cloud Tools:** Pre-built MCP tools for core GCS & BQ tasks.
*   🔗 **Scalable GCS I/O:** Uses **GCS Signed URLs** for direct, high-performance client uploads/downloads.
*   ⏳ **Resilient Async BigQuery:** Submits BQ queries without blocking; tracks status persistently in **Firestore**; client polls server efficiently.
*   ✅ **Stateless & Scalable:** Designed for horizontal scaling in cloud environments (Cloud Run, GKE).
*   🔒 **Secure Foundation:** Leverages **ADC** for GCP auth; supports **Secret Manager** for API keys.
*   ✨ **NEW in v1.1.0:**
    *   🏥 **Health Check Endpoint:** Includes `/healthz` for Kubernetes/Cloud Run readiness probes.
    *   ⏱️ **Basic Performance Insights:** Logs execution times for key operations.
    *   ⚙️ **Configurable URL Expiry:** Control Signed URL validity via environment variables.
    *   🧹 **Automatic Job Cleanup:** Optional background task removes old BQ job records from Firestore.

## Use Cases

*   **Document Q&A:** Agents fetch documents from GCS via Signed URLs for analysis.
*   **Data Analysis Assistant:** Agents run complex BQ queries asynchronously, check status, and retrieve results for users.
*   **Automated Reporting:** Agents generate reports and upload them directly to GCS using write Signed URLs.
*   **Cloud Resource Browser:** Agents help users navigate GCS/BQ by listing buckets, datasets, tables, etc.

## Who Benefits?

*   **AI Agent Developers (ADK, LangChain, etc.):** Add powerful, scalable cloud capabilities quickly.
*   **MCP Application Builders:** Need a reliable GCP backend via MCP? Use `mcp.agent`.
*   **Platform Teams:** Offer standardized, secure GCP tool access to internal teams building agents.
*   **DevOps Engineers:** Deploy and manage GCP integration easily via containers and standard health checks.

## Technical Highlights (v1.1.0)

*   Stateless Context Design
*   Firestore-backed BQ Job State
*   GCS Signed URLs for I/O
*   Asyncio Core with Thread Pool for Blocking Calls
*   ADC Authentication & Secret Manager Integration
*   Containerized (Dockerfile included)
*   Structured JSON Logging **with basic timing**
*   `tenacity`-based Retries for GCP calls
*   `/healthz` Endpoint **(New)**
*   Configurable URL Expiry **(New)**
*   Optional BQ Job Cleanup Task **(New)**

## Get Started with v1.1.0!

  **Prerequisites:** Python 3.9+, GCP Project, Enabled APIs (GCS, BQ, Firestore, Secret Manager), ADC Auth (`gcloud auth ...`), IAM Roles set.
  **Install:** `pip install .` from source (after updating dependencies).
  **Configure:** Set optional `MCP_AGENT_API_KEY_SECRET_NAME` / `MCP_AGENT_API_KEY`, and new optional env vars like `SIGNED_URL_EXPIRY_SECONDS`, `ENABLE_BQ_JOB_CLEANUP` in `.env`.
  **Run Server:** `mcp-agent --tools storage,bigquery --port 8080 [options]`
  **Connect Client:** Use MCP client libraries (ADK, `mcp`) with server connection details.
  **Interact:** Call tools, remembering clients must provide resource IDs and handle Signed URLs / BQ polling logic.

**Dive Deeper:**

*   **Quick Guide:** `INTRO.md`
*   **Detailed Usage:** `USAGE.md` (Ensure client logic examples are updated for v1.1.0 if necessary)
*   **Architecture:** `TECHNICAL.md`
*   **Constraints:** `Limitations.md` (Updated for v1.1.0)

---

> **Status:** `mcp.agent` v1.1.0 is an **Improved Beta**. It adds operational features making it more suitable for advanced testing and internal deployments. However, comprehensive production hardening (advanced security, full monitoring/alerting, load testing) is still recommended. See `PRODUCTION_DEPLOYMENT.md` guidance. Feedback and contributions remain welcome!

# .prompt
```txt
Update version number and tagline
Refresh "Why Use" section to include the new features
update "Technical insight"
adjust tone to convey incremental improvement
maintain core messaging and structure
```


