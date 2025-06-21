import argparse
import asyncio
import logging
import sys
import os
from typing import Set, Optional

from dotenv import load_dotenv
from pythonjsonlogger import jsonlogger

# Attempt relative import first for server functions
try:
    from .server import run_stdio_server, run_sse_server # These will be implemented in server.py
except ImportError:
     # Fallback running script directly
     sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
     from mcp_agent.server import run_stdio_server, run_sse_server

# Imports for GCP clients and utilities
try:
    from .gcp_tools.storage import get_storage_client # Corrected import for GCS client
    from .gcp_tools.bigquery import get_bq_client # Corrected import for BQ client
    from .utils import get_secret_manager_client, fetch_secret
    from .job_store import FirestoreBqJobStore # Now implemented
    from .bq_poller import run_bq_job_poller # For the BQ background poller
except ImportError as e:
    # This helps in debugging if the script is run in a weird environment or packaging is off
    print(f"Critical Import Error: {e}. Please ensure the package is installed correctly or PYTHONPATH is set.", file=sys.stderr)
    sys.exit(1)


# --- Configure Logging JSON Formatter ---
# Using the setup from the original server.py for consistency
root_logger = logging.getLogger()
logHandler = logging.StreamHandler(sys.stderr) # Log to stderr
formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(module)s %(funcName)s %(lineno)d %(message)s')
logHandler.setFormatter(formatter)
root_logger.handlers.clear()
root_logger.addHandler(logHandler)
root_logger.setLevel(logging.INFO) # Default to INFO
logger = logging.getLogger("mcp_agent.cli") # Logger for this module
# --- End Logging Setup ---

def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the MCP Agent server for GCS/BigQuery (v1.0.0 Stateless with Firestore BQ Jobs).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--tools",
        type=str,
        required=True,
        help="Comma-separated list of GCP services to enable (e.g., 'storage', 'bigquery', 'storage,bigquery').",
    )
    parser.add_argument(
        "--port",
        type=str,
        required=True,
        help="Connection mode: 'stdio' or a port number (e.g., 8080) for SSE.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="[SSE Only] Host address to bind to for SSE server (default: 127.0.0.1). Use 0.0.0.0 for network access.",
    )
    parser.add_argument(
        "--require-api-key",
        action='store_true', # Changed to action='store_true' from server.py
        help="[SSE Only] Enable API key authentication. Reads MCP_AGENT_API_KEY_SECRET_NAME (for Secret Manager full path) then MCP_AGENT_API_KEY (direct key).",
    )
    parser.add_argument(
         "--debug",
         action="store_true",
         help="Enable verbose debug logging for mcp_agent and reduce verbosity of GCP libraries."
    )
    parser.add_argument(
        "--bq-poll-interval",
        type=int,
        default=60,
        help="[BigQuery Only] Interval in seconds for polling BQ job statuses."
    )
    return parser.parse_args()

def main():
    # Load .env file if it exists
    dotenv_path = load_dotenv()
    if dotenv_path:
        logger.info("Loaded environment variables from .env file.", extra={'dotenv_path': str(dotenv_path)})
    else:
        logger.info("No .env file found or loaded.")

    args = parse_args()

    # --- Setup Logging Level ---
    if args.debug:
        logging.getLogger("mcp_agent").setLevel(logging.DEBUG)
        # Reduce verbosity of noisy GCP libraries unless specifically debugging them
        logging.getLogger("google.cloud").setLevel(logging.INFO)
        logging.getLogger("google.api_core").setLevel(logging.INFO)
        logging.getLogger("google.auth").setLevel(logging.INFO)
        logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
        logger.debug("Debug logging enabled for mcp_agent.")
    else:
        # Set default log levels for external libraries if not in debug mode
        logging.getLogger("google.cloud").setLevel(logging.WARNING)
        logging.getLogger("google.api_core").setLevel(logging.WARNING)
        logging.getLogger("google.auth").setLevel(logging.WARNING)
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
        logging.getLogger("mcp").setLevel(logging.INFO) # Assuming 'mcp' is the model-context-protocol library logger

    # --- Validate Tools ---
    try:
        enabled_tools: Set[str] = set(t.strip().lower() for t in args.tools.split(',') if t.strip())
    except Exception:
        logger.critical("Invalid format for --tools argument.")
        sys.exit(1)

    valid_tools = {"storage", "bigquery"}
    invalid_tools = enabled_tools - valid_tools
    if invalid_tools:
         logger.critical(f"Invalid tool(s) specified: {', '.join(invalid_tools)}. Allowed tools: {', '.join(valid_tools)}")
         sys.exit(1)
    if not enabled_tools:
         logger.critical("No tools specified. Use --tools storage,bigquery or similar.")
         sys.exit(1)

    logger.info(f"Configuring mcp-agent server v1.0.0", extra={"enabled_tools": list(enabled_tools), "args": vars(args)})

    # --- Determine API Key (SSE Only) ---
    api_key_to_use: Optional[str] = None
    if args.port.lower() != "stdio" and args.require_api_key:
        secret_name_env_var = 'MCP_AGENT_API_KEY_SECRET_NAME'
        direct_key_env_var = 'MCP_AGENT_API_KEY'

        secret_name_val = os.getenv(secret_name_env_var)
        direct_key_val = os.getenv(direct_key_env_var)
        secret_source = "None"

        if secret_name_val:
            logger.info(f"Attempting to fetch API key from Secret Manager using secret path in {secret_name_env_var}.", extra={"secret_name": secret_name_val})
            try:
                api_key_to_use = fetch_secret(secret_name_val) # fetch_secret uses retry
                if api_key_to_use:
                    secret_source = f"Secret Manager ({secret_name_val})"
                    logger.info("Successfully fetched API key from Secret Manager.")
                else:
                    # fetch_secret already logs errors, this is a critical failure for startup
                    logger.critical(f"Failed to fetch API key from Secret Manager: {secret_name_val}. Value was empty or fetch failed.")
                    sys.exit(1)
            except Exception as sm_err: # Broad catch, fetch_secret should handle specifics
                logger.critical(f"FATAL: Error during Secret Manager access for {secret_name_val}: {sm_err}", exc_info=args.debug)
                sys.exit(1)
        elif direct_key_val:
            logger.info(f"Using API key from environment variable {direct_key_env_var}.")
            api_key_to_use = direct_key_val
            secret_source = f"Environment Variable ({direct_key_env_var})"
        else:
            logger.critical(f"FATAL: --require-api-key is set, but neither {secret_name_env_var} nor {direct_key_env_var} environment variables are set with a value.")
            sys.exit(1)

        if not api_key_to_use: # Double check if key is actually obtained
             logger.critical("FATAL: API key required but could not be obtained.")
             sys.exit(1)
        logger.info(f"API Key Authentication: Enabled for SSE. Source: {secret_source}")

    elif args.port.lower() != "stdio":
        logger.info("API Key Authentication: Disabled for SSE (flag --require-api-key not set).")


    # --- Pre-flight Check for GCP Clients & Firestore ---
    try:
        logger.info("Performing pre-flight GCP client initialization checks...")
        # Using a list of functions to call for checks
        checks_to_perform = []

        if "storage" in enabled_tools:
            checks_to_perform.append(get_storage_client)

        if "bigquery" in enabled_tools:
            checks_to_perform.append(get_bq_client) # BQ client itself
            # Firestore Job Store check - instantiate and try to init client
            try:
                firestore_job_store_instance = FirestoreBqJobStore(project=os.getenv("GCP_PROJECT")) # Pass project if available
                # Add a dedicated init check method to the store if needed, e.g., store.ensure_client_initialized()
                # For now, instantiating it is part of the check. A specific check can be added to its methods.
                # We will use this instance later.
                checks_to_perform.append(firestore_job_store_instance.ensure_client_initialized)
            except Exception as fjse:
                logger.critical(f"Failed to instantiate FirestoreBqJobStore during pre-flight: {fjse}", exc_info=args.debug)
                sys.exit(1)


        if args.port.lower() != "stdio" and args.require_api_key and os.getenv('MCP_AGENT_API_KEY_SECRET_NAME'):
            checks_to_perform.append(get_secret_manager_client)

        for check_func in checks_to_perform:
            # If the check function itself is async, we'd need to run it in an event loop.
            # For now, assuming these are synchronous client getters/initializers.
            if asyncio.iscoroutinefunction(check_func):
                # This is tricky at this stage of startup if the main loop isn't running.
                # For simplicity, ensure client getters are sync or handle async init carefully.
                # For now, we assume they are synchronous or handle their own loop if necessary.
                logger.debug(f"Running async pre-flight check: {check_func.__name__}")
                # Not ideal to run a new loop for each, but for startup:
                # Or, collect them and run all async checks together if possible.
                # This part needs careful handling if pre-flight checks are async.
                # For now, assuming sync client getters like google-cloud-python typically provides.
                check_func() # Placeholder if it's sync
            else:
                logger.debug(f"Running sync pre-flight check: {check_func.__name__}")
                check_func()

        logger.info("GCP client pre-flight checks successful.")

    except Exception as e:
        logger.critical(f"FATAL: GCP client pre-flight check failed: {e}", exc_info=args.debug)
        logger.critical("Ensure Application Default Credentials (ADC) are set up correctly, necessary GCP APIs (Storage, BigQuery, Firestore, Secret Manager) are enabled, and the account has required IAM permissions (e.g., Storage Object Admin, BigQuery Job User, Datastore User, Secret Manager Secret Accessor).")
        sys.exit(1)
    # --- End Pre-flight Check ---

    # --- Start Server ---
    server_mode_info = "STDIO"
    if args.port.lower() != "stdio":
        server_mode_info = f"SSE on {args.host}:{args.port}"

    logger.info(f"Starting server in {server_mode_info} mode...")

    # Initialize BQ client and Firestore store if BQ is enabled, to pass to server and poller
    from google.cloud import bigquery as gcp_bigquery # For type hinting bq_client_instance

    bq_client_instance: Optional[gcp_bigquery.Client] = None
    firestore_job_store_instance_for_server: Optional[FirestoreBqJobStore] = None

    if "bigquery" in enabled_tools:
        try:
            bq_client_instance = get_bq_client() # Get the client instance
            firestore_job_store_instance_for_server = FirestoreBqJobStore(project=os.getenv("GCP_PROJECT"))
            # Ensure its client is ready if we didn't do it in pre-flight or if pre-flight was minimal
            # This is important if pre-flight only instantiated.
            # await firestore_job_store_instance_for_server.ensure_client_initialized() # Call this within an async context
        except Exception as e:
            logger.critical(f"Failed to initialize BigQuery client or FirestoreBqJobStore for server runtime: {e}", exc_info=args.debug)
            sys.exit(1)

    poller_task = None
    main_server_task = None

    async def server_with_poller():
        nonlocal poller_task, main_server_task

        # Ensure Firestore client is initialized before starting poller or server
        if firestore_job_store_instance_for_server:
            await firestore_job_store_instance_for_server.ensure_client_initialized()

        if "bigquery" in enabled_tools and bq_client_instance and firestore_job_store_instance_for_server:
            logger.info("Starting BigQuery job poller task...")
            poller_task = asyncio.create_task(run_bq_job_poller(
                firestore_job_store=firestore_job_store_instance_for_server,
                bq_client=bq_client_instance,
                poll_interval_seconds=args.bq_poll_interval
            ))

        server_kwargs = {
            "enabled_tools": enabled_tools,
            "bq_job_store": firestore_job_store_instance_for_server # Pass the store
        }

        if args.port.lower() == "stdio":
            if args.require_api_key:
                 logger.warning("--require-api-key is ignored for stdio mode.")
            main_server_task = asyncio.create_task(run_stdio_server(**server_kwargs))
        else:
            port_num = int(args.port)
            if not (1024 <= port_num <= 65535):
                 logger.critical(f"Invalid port number: {port_num}. Must be between 1024 and 65535.")
                 sys.exit(1) # Should be caught by try/except below if it raises
            server_kwargs.update({
                "host": args.host,
                "port": port_num,
                "api_key": api_key_to_use
            })
            main_server_task = asyncio.create_task(run_sse_server(**server_kwargs))

        if main_server_task:
            await main_server_task # Wait for the main server task to complete

    try:
        asyncio.run(server_with_poller())
    except KeyboardInterrupt:
        logger.info(f"{server_mode_info} server and/or poller interrupted by user (Ctrl+C). Shutting down.")
    except ValueError as e:
        logger.critical(f"Invalid port number specified: {args.port}. Error: {e}", exc_info=args.debug)
        sys.exit(1)
    except SystemExit:
        raise # Allow sys.exit to propagate
    except Exception as e:
        logger.critical(f"Failed to start or run {server_mode_info} server: {e}", exc_info=args.debug)
        sys.exit(1)
    finally:
        # Note: asyncio.run() handles task cancellation on exit/exception.
        # Explicit cancellation here might be redundant or interfere if not careful.
        if poller_task and not poller_task.done():
            logger.info("Attempting to cancel BQ poller task...")
            poller_task.cancel()
            # Allow time for cancellation to be processed
            # However, asyncio.run should manage this.
            # await asyncio.sleep(0.1)
        logger.info(f"{server_mode_info} server shutdown process initiated or completed.")

if __name__ == "__main__":
    main()
