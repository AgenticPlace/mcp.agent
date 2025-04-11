# Limitations of `mcp.agent` (v1.0.0 - Stateless Context, Firestore BQ Jobs)

This document outlines the known limitations and design constraints of the `mcp.agent` tool, version 1.0.0. Understanding these is crucial for effective use and identifying when alternatives (like using GCP SDKs directly or building custom MCP servers) are more appropriate. **This version introduces stateless context management and relies on Firestore for BQ job tracking.**

## 1. GCP Service Coverage

*   **Explicit Support Limited to GCS & BigQuery:** `mcp.agent` remains focused on Google Cloud Storage (GCS) and BigQuery (BQ). Support for other services is **not** included.
*   **Unsupported Services:** There are **no** pre-built tools for other GCP services (Vertex AI, Pub/Sub, Cloud Functions, Spanner, Secret Manager, etc.).
*   **Implication:** Cannot use `mcp.agent` for unsupported services via MCP without custom development.
*   **Workaround:** Use official GCP SDKs directly or build a custom MCP server.

## 2. Tool Functionality & Granularity

*   **Focus on Common Operations:** Provided tools cover frequent use cases but omit many advanced parameters available in the full GCP SDKs (e.g., specific storage classes, CMEK, detailed BQ job config like destination table, query parameters).
*   **GCS I/O via Signed URLs:** Large file reads/writes rely entirely on Signed URLs (`gcs_get_read_signed_url`, `gcs_get_write_signed_url`). The client application **must** handle the actual HTTP GET/PUT request directly to GCS.
*   **GCS Small String Writes Only:** The `gcs_write_string_object` tool only supports small string uploads directly through the server.
*   **No Tool Customization:** Toolset is fixed. Cannot modify behavior or combine GCP calls within `mcp.agent`.
*   **Implication:** Insufficient for fine-grained GCP API control or features beyond the basics.
*   **Workaround:** Use official GCP SDKs directly or build a custom MCP server.

## 3. Authentication Mechanism

*   **Primary Mechanism: Server-Side ADC:** Relies almost exclusively on Application Default Credentials (ADC) in the server's environment.
*   **No Per-Request User Impersonation:** All GCP actions use the *server's* identity.
*   **Implication:** Cannot enforce end-user-specific GCP permissions via `mcp.agent`.

## 4. State Management & Scalability

*   **Stateless User Context:** The server **does not** store default buckets or datasets per connection. This improves scalability but requires clients to manage their own context.
*   **BQ Job State in Firestore:** Asynchronous BQ job status (`PENDING`, `RUNNING`, `DONE`, `ERROR`) is stored persistently in Firestore.
    *   **Dependency:** Requires Firestore API enabled and appropriate IAM roles (`roles/datastore.user`) for the server's service account. Adds a dependency on another GCP service.
    *   **Durability:** Job state survives server restarts and across multiple instances.
    *   **Potential Cost:** Firestore usage costs apply, potentially significant with very high job volume.
    *   **Polling Overhead:** The background server poller queries Firestore periodically, adding some load. **Firestore indexes** on `status` and `last_update_time` fields are recommended for efficient querying at scale.
*   **Stdio Mode Limitation:** Single client, local use only. **Does not scale.**
*   **SSE Scaling:** Statelessness simplifies horizontal scaling (no need for session affinity), but requires standard infrastructure (containers, orchestrators, load balancers).

## 5. Client Responsibilities - *Increased in v1.0.0*

*   **Context Management:** The **client MUST track** its own working context (current bucket, dataset, project) and **provide the required identifiers** (`bucket_name`, `project_id`, `dataset_id`) in every relevant tool call.
*   **GCS I/O Handling:** The **client MUST implement HTTP logic** to download from or upload to the Signed URLs provided by `gcs_get_read_signed_url` and `gcs_get_write_signed_url`.
*   **BQ Async Polling:** The **client MUST implement polling logic** for asynchronous queries: call `bq_submit_query` -> store `job_id`/`location` -> periodically call `bq_get_job_status` -> check `state` -> if `DONE`, process first page results -> if `next_page_token`, call `bq_get_query_results` repeatedly.

## 6. Asynchronous Operation Handling (BigQuery)

*   **Async BQ Pattern (Client Polling):** Uses `bq_submit_query` -> `bq_get_job_status` -> `bq_get_query_results`.
*   **Implication:** The **client application or agent MUST implement polling logic** to check job status before attempting to fetch results. This shifts complexity from the server to the client compared to a simple blocking call.
*   **Server Poller:** The server polls GCP BQ in the background to update Firestore, but the client polls the *server's status tool*.

## 7. Error Reporting & Retries

*   **Simplified Error Propagation:** Standardized JSON errors (`status`, `message`), may mask full GCP error details.
*   **Built-in Retries:** Tools include retries (via `tenacity`) for *transient* GCP errors (5xx, 429, etc.) on backend calls. Non-retryable errors (NotFound, Forbidden, BadRequest) are returned immediately after the first attempt. Client-side retries might still be needed for *MCP communication* issues or around the BQ polling loop.

## 8. Deployment and Security

*   **Permissions Tied to Server Identity:** Security relies on correctly scoped IAM permissions for the server's ADC (including GCS, BQ, **Firestore**, **Secret Manager**, and **Service Account Token Creator**).
*   **Network Exposure (SSE):** Requires standard network security (firewalls, VPC, HTTPS via LB/Ingress).
*   **Basic SSE Authentication:** Optional API key (managed via env var/Secret Manager + flag) provides minimal protection. **Not sufficient for untrusted environments.** Stronger methods (IAP, mTLS, OAuth) needed for production.
*   **Input Validation:** Basic validation added for object paths, but comprehensive sanitization against all potential misuse is not guaranteed.

## Conclusion (v1.0.0)

`mcp.agent` (v1.0.0) offers a more scalable approach by removing server-side user context and using Firestore for durable BQ job tracking. GCS I/O uses efficient Signed URLs. However, this version significantly **increases client-side responsibilities** for managing context, handling HTTP transfers for GCS, and implementing the BQ polling workflow. It remains a proof-of-concept unsuitable for production without addressing comprehensive testing, security hardening, monitoring, and potentially more robust async/streaming patterns. Carefully evaluate the trade-offs between server simplicity/scalability and increased client complexity.
