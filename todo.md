# MCP Agent - TODO List

This document outlines tasks to improve the `mcp-agent` codebase, fix critical issues, and align it with the v1.0.0 specification in the `README.md`.

**Legend:**
*   `[x]` - Completed
*   `[~]` - Partially Completed / In Progress
*   `[ ]` - Not Started

## priority-1 Critical Bugs & Missing Features

These items prevent the agent from functioning as described in `README.md v1.0.0`.

*   **[x] Implement `FirestoreBqJobStore` Class:**
    *   Created the `FirestoreBqJobStore` class in `mcp_agent/job_store.py`.
    *   Defined methods: `add_job`, `get_job`, `update_job_status`, `query_pending_jobs`.
*   **[x] Define `BqJobInfo` Dataclass/TypedDict:**
    *   Created `BqJobInfo` dataclass in `mcp_agent/job_store.py`.
    *   Fields include `job_id`, `location`, `conn_id`, `status`, `error_result`, `created_time`, `updated_time`, `project_id`, `query`.
*   **[x] Implement GCS Signed URL Tools:**
    *   Implemented GCS tools (`gcs_list_buckets`, `gcs_list_objects`, `gcs_get_read_signed_url`, `gcs_get_write_signed_url`, `gcs_write_string_object`) in `mcp_agent/gcp_tools/storage.py`.
*   **[x] Implement Background BQ Job Poller:**
    *   Implemented in `mcp_agent/bq_poller.py`.
    *   Started as an asyncio task in `mcp_agent/cli.py`.
    *   Periodically queries Firestore, checks BQ API, and updates Firestore.
*   **[x] Implement Core Server Functions (`run_stdio_server`, `run_sse_server`):** (Moved from "Unknowns" as it was a critical missing piece)
    *   Implemented basic STDIO server loop in `mcp_agent/server.py`.
    *   Implemented SSE server using `aiohttp` in `mcp_agent/server.py`.
    *   Includes basic `dispatch_tool` logic.

## priority-2 Refactoring & Cleanup

Improve code structure, clarity, and remove inconsistencies.

*   **[x] Rename BigQuery Tools File:**
    *   Renamed `mcp_agent/gcp_tools/storage.py` (old BQ logic) to `mcp_agent/gcp_tools/bigquery.py`.
*   **[x] Rename GCS Tools File:** (New task based on implementation)
    *   Renamed `mcp_agent/gcp_tools/gcs_tools_temp.py` to `mcp_agent/gcp_tools/storage.py`.
*   **[x] Consolidate Tool Definitions:**
    *   Updated `mcp_agent/gcp_tools/__init__.py` to import new stateless tools and define `ALL_TOOLS_MAP` pointing to them.
    *   Schemas for advertisement are TBD (moved to a new P4 task).
*   **[x] Correct Import Paths:**
    *   Updated import statements in `cli.py`, `server.py`, and `gcp_tools/__init__.py`.
*   **[x] Remove Legacy Code:**
    *   Deleted `mcp_agent/context.py`.
    *   Old content of `mcp_agent/gcp_tools/__init__.py` was overwritten.
*   **[x] Clarify/Refactor `mcp_agent/server.py`:**
    *   `cli.py` is now the sole entry point.
    *   `server.py` now contains the core server logic (`run_stdio_server`, `run_sse_server`, `dispatch_tool`).
    *   Redundant CLI parsing and pre-flight checks removed from `server.py`.
*   **[x] Ensure Consistent Client Initialization:**
    *   `get_storage_client()` is in `mcp_agent/gcp_tools/storage.py`.
    *   `get_bq_client()` is in `mcp_agent/gcp_tools/bigquery.py`.
    *   `cli.py` calls these for pre-flight checks.

## priority-3 Code Quality & Best Practices

General improvements for maintainability.

*   **[x] Consistent Logging Names:**
    *   Verified and ensured consistent logger names across modules.
*   **[~] Type Hinting:**
    *   Added and reviewed type hints in new and modified code. Further enhancements for complex dicts can be a future task.
*   **[x] Error Handling:**
    *   Reviewed error handling in new tool implementations; uses `format_error` and `handle_gcp_error`.
*   **[x] Configuration Management:**
    *   Verified handling of GCP project, API key.
    *   Made BQ poller interval configurable via CLI.

## priority-4 Documentation

Updates to reflect the fixed and intended state.

*   **[x] Update `README.md`:**
    *   Updated "How it Works", "Tool Reference", "Installation", and "Usage" sections to reflect current architecture and implemented tools.
*   **[x] Inline Code Comments:**
    *   Added/improved comments in `server.py`, `bq_poller.py`, `job_store.py`, and `cli.py`.
*   **[ ] Define MCP Tool Schemas:** (New task, moved from P2 "Consolidate Tool Definitions")
    *   Populate `mcp_agent/gcp_tools/__init__.py` (or a separate schemas file) with `mcp_types.Tool` definitions for all implemented stateless tools. This is needed for proper client-side tool advertisement and argument understanding.

## Unknowns / Needs Clarification

*   **[x] Origin of `run_stdio_server` and `run_sse_server`:**
    *   These have been implemented in `mcp_agent/server.py`.

## New Potential Tasks (Post-MVP)

*   **[ ] Thorough Testing:** Implement unit and integration tests for tools, job store, poller, and server logic.
*   **[ ] Advanced Error Handling:** More granular error codes/types in MCP responses.
*   **[ ] Tool Schema Generation:** Automate or more systematically define MCP tool schemas in `gcp_tools/__init__.py`.
*   **[ ] Configuration for Firestore Collection:** Allow `mcp_agent_bq_jobs` collection name to be configurable.
*   **[ ] More Robust Pre-flight Checks:** Deeper checks for IAM permissions if possible.
*   **[ ] Scalability Testing for Poller:** Evaluate poller performance under high load.

This TODO list should guide the process of making `mcp-agent` a functional and maintainable tool.
