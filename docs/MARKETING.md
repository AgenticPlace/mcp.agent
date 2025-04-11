# `mcp.agent`: Connect Your MCP Agents to Google Cloud Instantly!

**(v1.0.0 - Beta)**

<p align="center">
  <img src="placeholder_logo.png" alt="mcp.agent Logo Placeholder" width="200"/>
</p>

**Focus on Agent Intelligence, Not Cloud Plumbing.**

## The Challenge: Agents Need Cloud Power

Building intelligent agents often requires accessing vast data stores or powerful cloud services. Integrating Google Cloud Storage (GCS) or BigQuery (BQ) directly into your agent application using the Model Context Protocol (MCP) can mean writing significant boilerplate code:

*   Setting up and managing a dedicated MCP server.
*   Wrapping complex GCP SDK calls into MCP tool definitions.
*   Handling secure Google Cloud authentication.
*   Managing state across interactions (like the current bucket).
*   Dealing with long-running operations or large file transfers efficiently.

This plumbing distracts from building the core intelligence and capabilities of your agent.

## The Solution: `mcp.agent` - Your GCP<->MCP Bridge

`mcp.agent` is a ready-to-run MCP server specifically designed to bridge the gap between your MCP clients (like ADK agents) and core Google Cloud services (GCS & BQ).

Run `mcp.agent` with a single command, and instantly equip your agents with tools to interact with buckets, objects, datasets, tables, and even run asynchronous BigQuery jobs, all through the standard MCP interface.

## Why Use `mcp.agent`?

*   🚀 **Launch in Minutes:** Forget writing server code. Deploy a containerized MCP server for GCS/BQ instantly.
*   🛠️ **Essential Cloud Tools:** Provides pre-built MCP tools for common GCS and BigQuery operations out-of-the-box.
*   🔗 **Scalable File Handling:** Leverages efficient GCS Signed URLs for direct, secure client uploads and downloads – handles large files without bottlenecking the server.
*   ⏳ **Non-Blocking BigQuery:** Submit long-running BigQuery jobs asynchronously. `mcp.agent` tracks job status persistently in Firestore, allowing your client to poll efficiently without blocking.
*   ✅ **Built for Scale:** The stateless v1.0.0 design (no server-side user context) makes `mcp.agent` easier to scale horizontally using standard cloud infrastructure.
*   🔒 **Secure by Default:** Uses Google Cloud's standard Application Default Credentials (ADC) for secure server-side authentication to GCP. Supports secure API key management via Secret Manager.
*   🧩 **MCP Standard:** Connect any MCP-compliant client seamlessly.

## Use Cases

Empower your agents to:

*   💾 **Read configuration or data files** directly from GCS buckets.
*   📄 **Retrieve and summarize documents** stored in GCS.
*   📦 **Archive generated reports or user data** to specific GCS locations.
*   📊 **Query BigQuery datasets** based on user requests or agent analysis.
*   📈 **Fetch results from complex, long-running BigQuery analyses** asynchronously.
*   🗂️ **List available datasets, tables, or buckets** to assist users.

## Who Is It For?

*   **AI Agent Developers:** Quickly add GCS & BQ capabilities to agents built with ADK or other MCP frameworks.
*   **MCP Application Builders:** Need a standardized way to expose core GCP services via MCP? `mcp.agent` provides the server.
*   **Teams Prioritizing Speed:** Accelerate development by using a pre-built, focused GCP integration layer.

## Technical Highlights (v1.0.0)

*   **Stateless Context:** Server doesn't store user defaults (bucket/dataset), enhancing scalability.
*   **Firestore for BQ Jobs:** Durable tracking of async query status.
*   **GCS Signed URLs:** Offloads large data transfer directly between client and GCS.
*   **Asyncio Core:** Built for efficient I/O.
*   **ADC Authentication:** Securely uses GCP's standard authentication.
*   **Containerized:** Easy deployment via Docker.
*   **Structured Logging:** JSON logs for better observability.
*   **Retries:** Built-in resilience for transient GCP API errors.

## Get Started Today!

1.  **Read the Introduction:** `INTRO.md`
2.  **Follow the Usage Guide:** `USAGE.md`
3.  **Explore the Code:** (Link to Repository)
4.  **Understand the Boundaries:** `Limitations.md`

---

> **Status:** `mcp.agent` v1.0.0 is a significant step towards a scalable solution but remains a **Beta / Proof-of-Concept**. It requires further testing, security hardening, and feature refinement for robust production deployment. See `PRODUCTION_DEPLOYMENT.md` for considerations. Contributions and feedback are welcome!
Use code with caution.
Markdown
