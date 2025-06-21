# MCP Agent - TODO List

This document outlines tasks to improve the `mcp-agent` codebase, fix critical issues, and align it with the v1.0.0 specification in the `README.md`.

## priority-1 Critical Bugs & Missing Features

These items prevent the agent from functioning as described in `README.md v1.0.0`.

*   **[ ] Implement `FirestoreBqJobStore` Class:**
    *   Create the `FirestoreBqJobStore` class responsible for all Firestore interactions related to BigQuery job persistence (add, get, update job status).
    *   Define methods as implied by `README.md` and `bq_submit_query`/`bq_get_job_status` usage:
        *   `add_job(job_info: BqJobInfo)`
        *   `get_job(job_id: str) -> Optional[BqJobInfo]`
        *   `update_job_status(job_id: str, status: str, error_result: Optional[Dict] = None)`
        *   Potentially a method for the background poller to query pending jobs.
    *   **Location:** Consider placing this in `mcp_agent/job_store.py` (singular, as per README's implication for this class) or a new `mcp_agent/firestore_job_store.py`. Ensure imports are updated accordingly.
*   **[ ] Define `BqJobInfo` Dataclass/TypedDict:**
    *   Create a `BqJobInfo` structure (e.g., a dataclass or TypedDict) to represent BigQuery job details stored in Firestore.
    *   Fields should include `job_id`, `location`, `conn_id`, `status`, `error_result`, `created_time`, `updated_time`, etc.
    *   Used by `FirestoreBqJobStore` and BigQuery tool functions.
*   **[ ] Implement GCS Signed URL Tools:**
    *   Create the actual GCS tool implementations for generating signed URLs.
    *   Functions like `gcs_get_read_signed_url`, `gcs_get_write_signed_url` need to use `bucket.generate_signed_url()`.
    *   Other GCS tools (`gcs_list_buckets`, `gcs_list_objects`, `gcs_write_string_object`) also need their correct stateless implementations.
    *   **Location:** These should be in `mcp_agent/gcp_tools/storage.py`.
*   **[ ] Implement Background BQ Job Poller:**
    *   The `README.md` mentions a "background BQ poller task (reading from/writing to Firestore)". This logic needs to be implemented.
    *   It should periodically query Firestore for jobs not in a terminal state (DONE, ERROR), check their actual status via BQ API, and update Firestore via `FirestoreBqJobStore`.
    *   This poller should be started as an asyncio task when the server initializes (likely in `cli.py` or the actual server run functions).

## priority-2 Refactoring & Cleanup

Improve code structure, clarity, and remove inconsistencies.

*   **[ ] Rename BigQuery Tools File:**
    *   Rename `mcp_agent/gcp_tools/storage.py` (which currently contains BigQuery logic) to `mcp_agent/gcp_tools/bigquery.py`.
*   **[ ] Consolidate Tool Definitions:**
    *   The content of `mcp_agent/jobstore.py` (plural, defining tool schemas and `ALL_TOOLS_MAP` for v1.0.0) should become the content of `mcp_agent/gcp_tools/__init__.py`.
    *   This makes `mcp_agent/gcp_tools/` a proper Python package for all tool implementations and their definitions.
    *   Delete the now-redundant `mcp_agent/jobstore.py` (plural) after moving its content.
*   **[ ] Correct Import Paths:**
    *   Update all import statements affected by file renaming and restructuring. Examples:
        *   In `mcp_agent/cli.py`: Imports for `get_storage_client` (from the new `gcp_tools.storage`) and `get_bq_client` (from the new `gcp_tools.bigquery`).
        *   In `mcp_agent/gcp_tools/bigquery.py` (formerly `storage.py`): Import for `FirestoreBqJobStore` from its new correct location.
        *   In the new `mcp_agent/gcp_tools/__init__.py`: Imports for GCS functions from `.storage` and BQ functions from `.bigquery`.
*   **[ ] Remove Legacy Code:**
    *   Delete `mcp_agent/context.py` (`ConnectionContextManager`).
    *   Delete the old (stateful) content of `mcp_agent/gcp_tools/__init__.py` (before replacing it as per above).
*   **[ ] Clarify/Refactor `mcp_agent/server.py`:**
    *   Determine the true purpose of `mcp_agent/server.py`.
        *   If it's a redundant entry point to `cli.py`, remove it.
        *   If it's meant to contain core server helper functions used by `cli.py` (but not `run_stdio_server`/`run_sse_server` themselves if they are from an external lib), refactor it to only contain that logic and remove CLI parsing.
        *   The module-level instantiation of `FirestoreBqJobStore()` and pre-flight checks in this file are problematic and likely belong in `cli.py` or the server startup sequence.
*   **[ ] Ensure Consistent Client Initialization:**
    *   The `get_storage_client()` and `get_bq_client()` functions should be correctly defined in their respective modules (`gcp_tools/storage.py` and `gcp_tools/bigquery.py`).
    *   `cli.py` should call these for pre-flight checks.

## priority-3 Code Quality & Best Practices

General improvements for maintainability.

*   **[ ] Consistent Logging Names:**
    *   Ensure loggers use consistent naming conventions, e.g., `logging.getLogger("mcp_agent.gcp_tools.storage")` in `storage.py` and `logging.getLogger("mcp_agent.gcp_tools.bigquery")` in `bigquery.py`.
*   **[ ] Type Hinting:**
    *   Review and enhance type hints across the codebase for better clarity and static analysis. Particularly for `BqJobInfo` and complex dictionary structures.
*   **[ ] Error Handling:**
    *   Review error handling in tool implementations to ensure appropriate error messages are returned to the MCP client.
*   **[ ] Configuration Management:**
    *   Verify that all configurable parts (e.g., Firestore project/database if not default) are handled cleanly, possibly via environment variables or CLI arguments if necessary.

## priority-4 Documentation

Updates to reflect the fixed and intended state.

*   **[ ] Update `README.md`:**
    *   Clarify the roles of `cli.py` and the actual MCP server core logic (e.g., `run_stdio_server`, `run_sse_server` - specify if they are from an external library or should be part of this project's codebase).
    *   Correct file path references if they change significantly (e.g., `job_store.py` singular vs. plural, location of tool definitions).
    *   Ensure the "How it Works" section accurately reflects the (corrected) codebase.
*   **[ ] Inline Code Comments:**
    *   Add/improve comments in complex sections of the code, especially around Firestore interactions and the BQ polling logic.

## Unknowns / Needs Clarification

*   **Origin of `run_stdio_server` and `run_sse_server`:**
    *   `cli.py` imports these from `.server`. Are these functions expected to be defined within `mcp_agent/server.py`, or are they provided by an external `mcp.server` library that this project uses? If they are meant to be in this project, their definitions are missing. This needs clarification to understand the full scope of the server implementation.
    *   The `README.md`'s description of `server.py` as the "MCP Server Core" adds to this confusion.

This TODO list should guide the process of making `mcp-agent` a functional and maintainable tool.
