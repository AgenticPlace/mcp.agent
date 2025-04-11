# `mcp.agent` Developer Guide (v1.0.0)

Welcome, developer! This guide provides instructions and guidelines for setting up your development environment, running tests, understanding the codebase, and contributing to the `mcp.agent` project.

This assumes you have already reviewed the main `README.md` for the project's purpose and high-level features.

## Prerequisites

*   **Python:** 3.9+ (Check `pyproject.toml` for the exact minimum). Ensure `pip` and `venv` are available.
*   **Git:** For cloning the repository and version control.
*   **Google Cloud SDK (`gcloud`):** Required for setting up Application Default Credentials (ADC) locally. Install from [here](https://cloud.google.com/sdk/docs/install).
*   **Docker:** Required for building and running the container image (optional for basic development but needed for container testing/deployment).
*   **GCP Project & Enabled APIs:** You'll need access to a GCP project with the necessary APIs enabled (Storage, BigQuery, Firestore, Secret Manager) and appropriate IAM permissions to run the code against actual services during development or testing (even though unit/integration tests use mocks). See `README.md` prerequisites.

## Getting Started: Setting Up Your Environment

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url> # Replace with the actual URL
    cd mcp_agent
    ```

2.  **Create & Activate a Virtual Environment:**
    *It's strongly recommended to use a virtual environment to isolate dependencies.*
    ```bash
    # Create the environment (use .venv which is common in .gitignore)
    python -m venv .venv

    # Activate it (Linux/macOS)
    source .venv/bin/activate
    # Or (Windows - Git Bash / WSL)
    # source .venv/Scripts/activate
    # Or (Windows - Command Prompt)
    # .venv\Scripts\activate.bat
    # Or (Windows - PowerShell)
    # .venv\Scripts\Activate.ps1
    ```

3.  **Install Dependencies (including Test dependencies):**
    *Use the `-e` flag for editable mode, which links the installed package to your source code, allowing changes to be reflected immediately without reinstalling.*
    ```bash
    pip install --upgrade pip setuptools wheel # Ensure build tools are up-to-date
    pip install -e .[test]
    ```

4.  **Set up Local GCP Authentication (ADC):**
    *Log in with your Google account and set your default project.*
    ```bash
    gcloud auth application-default login
    gcloud config set project YOUR_DEVELOPMENT_PROJECT_ID
    ```

5.  **Configure `.env` File:**
    *   Copy the sample file: `cp .env.sample .env`
    *   Edit the `.env` file:
        *   If you plan to test SSE mode with API key authentication locally, uncomment and set `MCP_AGENT_API_KEY` to a test key. (Alternatively, set up a secret in Secret Manager and set `MCP_AGENT_API_KEY_SECRET_NAME`).
        *   You generally don't need `GCLOUD_PROJECT` or `GOOGLE_APPLICATION_CREDENTIALS` if you used `gcloud auth application-default login`.
    *   **Important:** Ensure `.env` is listed in your global or project `.gitignore` file.

## Running Locally for Development

You can run the server directly using the installed entry point script (`mcp-agent`) from your activated virtual environment.

*   **stdio mode (GCS & BQ):**
    ```bash
    mcp-agent --tools storage,bigquery --port stdio --debug
    ```
    *(Use `--debug` for verbose logging during development).*

*   **SSE mode (GCS only, Port 8080, with API Key from `.env`):**
    ```bash
    # Ensure MCP_AGENT_API_KEY or MCP_AGENT_API_KEY_SECRET_NAME is set in .env
    mcp-agent --tools storage --port 8080 --host 127.0.0.1 --require-api-key --debug
    ```

*Stop the server with `Ctrl+C`.*

## Running Tests

The project uses `pytest`. Tests are located in the `tests/` directory.

1.  **Ensure Test Dependencies Are Installed:** (Done via `pip install -e .[test]`).
2.  **Run Tests:** From the project root directory:
    ```bash
    pytest
    ```
    *   Add `-v` for more verbose output.
    *   Run specific files: `pytest tests/test_utils.py`
    *   Run specific tests using `-k`: `pytest -k "test_bq_submit_query"`

*Most tests use mocking and should run without hitting actual GCP APIs. However, ensure your environment is generally set up (like having ADC configured) as some tests might implicitly rely on library initialization steps.*

## Code Structure Overview

*   **`mcp_agent/`**: Main application source code.
    *   `cli.py`: Entry point, argument parsing, logging setup, server startup orchestration.
    *   `server.py`: Core `McpAgentServer` class, MCP handlers, background BQ poller.
    *   `job_store.py`: `FirestoreBqJobStore` for persistent BQ job state.
    *   `utils.py`: Helper functions (response formatting, error handling, Secret Manager access, retry logic).
    *   `gcp_tools/`: Modules implementing interactions with specific GCP services.
        *   `__init__.py`: Defines MCP tool schemas and maps tool names to functions.
        *   `storage.py`: GCS tool implementations (Signed URLs, etc.).
        *   `bigquery.py`: BQ tool implementations (Async pattern, etc.).
*   **`tests/`**: Unit and integration tests using `pytest`. Mirrors the source structure.
*   **`pyproject.toml`**: Project metadata, dependencies (runtime and test).
*   **`requirements.txt`**: Alternative dependency listing (generated from `pyproject.toml`).
*   **`Dockerfile`**: Container build definition.
*   **`.env.sample`**: Template for environment variables.
*   **`.dockerignore`, `.gitignore`**: Files excluded from Docker context / Git.
*   **`README.md`, `USAGE.md`, `TECHNICAL.md`, `Limitations.md`, `ROADMAP.md`, `DEV.md`**: Documentation.

➡️ For a detailed architectural breakdown, see `TECHNICAL.md`.

## Development Workflow & Contribution Guidelines

1.  **Branching:** Create feature branches from `main` (or `develop` if used):
    ```bash
    git checkout main
    git pull origin main
    git checkout -b feature/my-cool-new-tool
    ```
2.  **Code Style:**
    *   Follow PEP 8 guidelines.
    *   Use clear variable and function names.
    *   **TODO:** Set up linters (`flake8`) and formatters (`black`, `isort`) and add configuration files (`setup.cfg` or `pyproject.toml` sections) to enforce style automatically. Run these tools before committing.
    *   Write comprehensive **docstrings** for public modules, classes, and functions.
    *   Use **type hints** extensively.
3.  **Commits:** Write clear, concise commit messages. Consider using Conventional Commits format (e.g., `feat: Add tool for GCS lifecycle rules`, `fix: Correct pagination token handling`).
4.  **Testing:**
    *   **Write tests** (unit and/or integration) for new features or bug fixes in the `tests/` directory.
    *   Use mocking (`unittest.mock`, `pytest-mock`) appropriately to isolate components, especially GCP calls.
    *   Ensure **all tests pass** (`pytest`) before submitting changes.
5.  **Pull Requests (PRs):**
    *   Push your feature branch to the origin repository.
    *   Create a Pull Request targeting the `main` branch (or `develop`).
    *   Write a clear description of the changes, why they were made, and how they were tested.
    *   Link to relevant issues if applicable.
    *   Engage in the code review process.

## Building

*   **Python Package (Wheel/sdist):**
    ```bash
    # Ensure 'build' package is installed: pip install build
    python -m build
    # Artifacts will be in the 'dist/' directory
    ```
*   **Docker Image:**
    ```bash
    # From the project root directory
    docker build -t mcp-agent:latest .
    # Or use a specific version tag
    docker build -t your-repo/mcp-agent:1.0.0 .
    ```

## Future Development

Refer to `ROADMAP.md` for planned features and improvements. Feel free to suggest changes or contribute!
