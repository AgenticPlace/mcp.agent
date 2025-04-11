# `mcp.agent`: Production Deployment Considerations (v1.0.0)

> **⚠️ Important Note:** While labeled "v1.0.0" to mark a significant design milestone (stateless context, Firestore state), the provided `mcp.agent` codebase remains a **Beta-level Proof-of-Concept**. It requires significant hardening, testing, monitoring implementation, and security review before being suitable for critical production workloads. **Do not deploy directly to production without addressing the points below.**

This document outlines the critical areas needing attention to move the `mcp.agent` concept toward a reliable, secure, and scalable production deployment.

## 1. Deployment Strategy & Infrastructure

*   **Transport:**
    *   `stdio`: **Unsuitable for production.**
    *   `sse`: The only viable option provided. Requires appropriate infrastructure for termination, load balancing, and security.
*   **Containerization:** **Essential.** Use the provided `Dockerfile` as a starting point. Ensure the image is stored in a secure registry (e.g., Google Artifact Registry).
*   **Orchestration/Hosting Platform (GCP Recommended):**
    *   **Google Cloud Run:** Good fit due to the server's stateless nature regarding *user context*. Handles scaling (including to zero), HTTPS termination. Ideal for moderate load. Need to consider potential cold starts and ensure the Firestore dependency is handled correctly.
    *   **Google Kubernetes Engine (GKE):** Provides maximum control for complex scaling scenarios, fine-grained networking, and managing potentially long-lived SSE connections if needed (though less critical with stateless design). Requires more operational overhead.
    *   **Compute Engine (GCE):** Requires manual setup for process management (`systemd`), scaling, load balancing, health checks, and patching. Less recommended unless specific VM control is needed.
*   **Process Management (if using GCE/VMs):** Use `systemd`, `supervisor`, or similar tools to ensure the `mcp-agent` process is reliable and restarts on failure.

## 2. Scalability & Availability

*   **Stateless Context Benefit:** Removing per-connection user context (bucket/dataset defaults) significantly simplifies horizontal scaling. Standard load balancing (without session affinity) can be used effectively as any instance can handle any request, provided the required identifiers are sent by the client.
*   **Multiple Instances:** Run multiple container instances across different zones (for availability) behind a load balancer.
*   **Autoscaling:** Configure autoscaling based on CPU, memory, or request count (e.g., via Cloud Run settings or GKE Horizontal Pod Autoscaler).
*   **Firestore Scaling:** Firestore scales automatically, but monitor performance and consider data modeling/indexing for the `mcp_agent_bq_jobs` collection, especially under high load (see Section 11).
*   **BQ Background Poller:** The single poller task within each instance might become a bottleneck if managing thousands of concurrent BQ jobs *per instance*. At very high scale, consider:
    *   Externalizing polling using Cloud Tasks or Cloud Scheduler + Cloud Functions, which query Firestore and update job status.
    *   Sharding jobs across different server instances or external pollers.
*   **Resource Limits:** Profile the application under load to determine appropriate CPU/Memory requests and limits for container instances.

## 3. Security Hardening

*   **Network Security:**
    *   Deploy within a **VPC**.
    *   Use **Firewall rules** to restrict ingress traffic to the SSE port only from trusted sources (load balancer IPs, specific VPC ranges, etc.).
*   **Transport Security (TLS/HTTPS):**
    *   **Mandatory.** Terminate TLS at the load balancer or managed service ingress (Cloud Run, GKE Ingress). Do not expose plain HTTP over untrusted networks.
*   **Authentication (SSE Transport):**
    *   The optional API key (`--require-api-key` flag + env var) provides **minimal protection**. Avoid relying solely on this for sensitive environments.
    *   **Recommended:** Use stronger mechanisms managed by your infrastructure:
        *   **Google Identity-Aware Proxy (IAP):** Securely proxy traffic, handling Google user or service account authentication *before* it reaches Cloud Run/GKE. Ideal for internal or workforce access.
        *   **Mutual TLS (mTLS):** For service-to-service communication where both client and server verify certificates. Requires setup on load balancer/ingress and client side.
        *   **OAuth/OIDC Integration:** If clients are associated with end-users, integrate a proper OAuth flow where the client obtains a token verified by the server or an intermediary proxy.
*   **GCP Permissions (Least Privilege):**
    *   Run `mcp.agent` using a **dedicated GCP Service Account**.
    *   Grant this SA **only the minimum required IAM roles**:
        *   GCS: e.g., `roles/storage.objectViewer`, `roles/storage.objectCreator` (as needed).
        *   BQ: e.g., `roles/bigquery.jobUser`, `roles/bigquery.dataViewer`.
        *   **Firestore:** `roles/datastore.user`.
        *   **Secret Manager:** `roles/secretmanager.secretAccessor` (if using for API key).
        *   **Self (for Signed URLs):** `roles/iam.serviceAccountTokenCreator` *on the service account itself*.
    *   Regularly audit permissions.
*   **Input Validation:**
    *   **CRITICAL:** Although basic path validation was added, rigorously sanitize and validate **ALL** inputs from MCP clients (`arguments` dict) before using them in *any* GCP API call (paths, query strings, IDs, parameters). Defend against injection, traversal, etc.

## 4. Authentication & Authorization (Application Level)

*   **Server-Side GCP Auth Only:** The design uses ADC for the server's identity. It **cannot** act on behalf of the MCP client user for GCP actions.
*   **Client Authorization:** If different MCP clients should have different permissions *within* `mcp.agent` (e.g., access specific tools or resources), this logic needs to be implemented separately, potentially based on verified client identity from a stronger authentication mechanism (like claims in an OIDC token passed via headers).

## 5. Error Handling & Resilience

*   **Retries:** `tenacity` provides retries for common transient GCP errors. Monitor logs to see if retry configurations need tuning (more attempts, different backoff, additional exception types).
*   **Non-Retryable Errors:** Ensure clear error messages are returned for non-retryable GCP errors (permissions, not found, bad requests) and client-side errors (missing required arguments).
*   **Graceful Shutdown:** Implement proper signal handling (`SIGTERM`, `SIGINT`) in the server process (likely within `cli.py`'s main execution block) to:
    *   Signal the BQ poller task to stop (`stop_poller`).
    *   Potentially allow in-flight MCP requests a brief period to finish (complex with async).
    *   Ensure logs are flushed.
*   **Health Checks:** Add a dedicated HTTP health check endpoint (e.g., `/healthz`) to the SSE server portion that orchestrators (Kubernetes, Cloud Run) can query to verify instance health beyond just basic port listening.

## 6. Monitoring & Logging

*   **Structured Logging:** JSON logging is implemented. Ensure logs are ingested into a centralized system (like Google Cloud Logging).
*   **Cloud Monitoring Metrics:** **CRITICAL.** Instrument the application to export key metrics using OpenTelemetry or Cloud Client Libraries for Monitoring:
    *   MCP Request Rate & Latency (per tool).
    *   Error Rate (per tool, per status code).
    *   GCP API Call Latency & Error Rate (per service/method).
    *   BQ Job Submission/Completion Rate.
    *   Firestore Interaction Latency/Errors.
    *   Instance Count, CPU/Memory Usage.
*   **Alerting:** Configure alerts in Cloud Monitoring based on thresholds for error rates, latency, resource usage, or unhealthy instance counts.

## 7. Asynchronous Operations (BigQuery)

*   **Client Polling Required:** The client **must** handle the `submit -> status -> results` polling logic. This needs clear documentation and potentially client-side helper libraries.
*   **Firestore Dependency:** The reliability of BQ job tracking now depends on Firestore availability and performance.

## 8. GCS Large File Handling (Signed URLs)

*   **Client HTTP Required:** The client **must** be capable of making HTTP GET (for downloads) and HTTP PUT (for uploads) requests directly to GCS using the provided Signed URLs.

## 9. Configuration Management

*   **Externalize Config:** Use environment variables (managed via `.env` locally, Cloud Run/GKE env vars, or mounted secrets/configmaps) for all configurable parameters (API keys via Secret Manager, potentially timeouts, log levels, Firestore collection names, retry settings). Avoid hardcoding.

## 10. Firestore Considerations

*   **Database Choice:** Ensure your Firestore instance is created in **Datastore mode** (required by the current client library usage, although Native mode could also work with adjustments).
*   **Indexing:** For the `mcp_agent_bq_jobs` collection, create composite indexes in Firestore, especially on `status` and `last_update_time`, to ensure efficient querying by the background poller and cleanup tasks at scale. Analyze query patterns.
*   **Cost:** Monitor Firestore reads/writes/deletes, especially from the background poller and cleanup jobs. High query volume could incur costs. Optimize polling frequency and cleanup logic.
*   **Data Retention/Cleanup:** Implement or schedule the `cleanup_old_jobs` function (or an equivalent external process like a Cloud Function on a schedule) to prevent the Firestore collection from growing indefinitely.

## 11. Testing

*   **Expand Coverage:** Significantly increase unit and integration test coverage, mocking external dependencies (GCP clients, Firestore).
*   **End-to-End (E2E) Tests:** Create automated tests that deploy `mcp.agent` to a test environment and run an MCP client against it to verify real interactions.
*   **Load Testing:** Simulate concurrent client connections and tool calls to identify performance bottlenecks and determine appropriate resource allocation and scaling parameters.

## Conclusion

Version 1.0.0 establishes a more scalable architectural foundation by removing per-connection state and externalizing BQ job tracking. However, **significant work remains across all areas**—especially security, monitoring, operational robustness, and comprehensive testing—before `mcp.agent` can be considered truly production-ready. Thoroughly address the points in this document based on your specific operational requirements and risk tolerance.
