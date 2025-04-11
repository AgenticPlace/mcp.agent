import argparse
import asyncio
import logging
import sys
import os
from typing import Set
from dotenv import load_dotenv
from pythonjsonlogger import jsonlogger

# Attempt relative import first
try:
    from .server import run_stdio_server, run_sse_server
    from .gcp_tools.storage import get_storage_client
    from .gcp_tools.bigquery import get_bq_client
    from .utils import get_secret_manager_client, fetch_secret
    from .job_store import FirestoreBqJobStore # Use Firestore store
except ImportError:
     # Fallback running script directly
     import os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
     from mcp_agent.server import run_stdio_server, run_sse_server
     from mcp_agent.gcp_tools.storage import get_storage_client
     from mcp_agent.gcp_tools.bigquery import get_bq_client
     from mcp_agent.utils import get_secret_manager_client, fetch_secret
     from mcp_agent.job_store import FirestoreBqJobStore


# --- Configure Logging JSON Formatter ---
root_logger = logging.getLogger(); logHandler = logging.StreamHandler(sys.stderr)
formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s %(pathname)s %(lineno)d')
logHandler.setFormatter(formatter); root_logger.handlers.clear(); root_logger.addHandler(logHandler)
root_logger.setLevel(logging.INFO); logger = logging.getLogger("mcp_agent.cli")
# --- End Logging Setup ---

# Create instance Firestore store enable pre flight check
# Note This assumes default Firestore database project
_firestore_job_store = FirestoreBqJobStore()

def parse_args():
    """Parses command line arguments MCP agent server"""
    parser = argparse.ArgumentParser(
        description="Run MCP Agent server GCS BQ v1 0 0 Stateless Firestore BQ Jobs", # Updated
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--tools", type=str, required=True, help="Comma separated storage bigquery")
    parser.add_argument("--port", type=str, required=True, help="Connection mode stdio or SSE port number")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="SSE Only Host address Use 0 0 0 0 network access")
    parser.add_argument("--require-api-key", action='store_true', help="SSE Only Enable API key auth Reads MCP AGENT API KEY SECRET NAME then MCP AGENT API KEY")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    return parser.parse_args()

def main() -> None:
    """Main entry point mcp agent command line tool"""
    dotenv_path = load_dotenv() # Load env file early
    if dotenv_path: logger.info("Loaded env vars from env file", extra={'dotenv_path': dotenv_path})
    else: logger.info("No env file found")
    args = parse_args()
    # --- Setup Logging Level ---
    log_level = logging.DEBUG if args.debug else logging.INFO # ... set levels ...
    logging.getLogger("mcp_agent").setLevel(log_level); # ... other logger levels ...
    if args.debug: logger.debug("Debug logging enabled")
    else: logging.getLogger("google").setLevel(logging.WARNING); logging.getLogger("mcp").setLevel(logging.INFO)

    # --- Validate Tools ---
    try: enabled_tools: Set[str] = set(t.strip().lower() for t in args.tools.split(',') if t.strip())
    except Exception: logger.critical("Invalid tools format"); sys.exit(1)
    valid_tools = {"storage", "bigquery"}; invalid_tools = enabled_tools - valid_tools
    if invalid_tools: logger.critical(f"Invalid tools {invalid_tools} Allowed {valid_tools}"); sys.exit(1)
    if not enabled_tools: logger.critical("No tools specified"); sys.exit(1)
    logger.info(f"Configuring mcp agent server v1 0 0", extra={"enabled_tools": list(enabled_tools)})

    # --- Determine API Key Secret Manager integration ---
    api_key_to_use: Optional[str] = None; secret_source: str = "None"
    if args.port.lower() != "stdio" and args.require_api_key:
        secret_name_var = os.getenv('MCP_AGENT_API_KEY_SECRET_NAME'); direct_key_var = os.getenv('MCP_AGENT_API_KEY')
        if secret_name_var:
            logger.info("Attempting fetch API key Secret Manager", extra={"secret_name": secret_name_var})
            try:
                # Fetch secret uses retry internally now
                api_key_to_use = fetch_secret(secret_name_var)
                if api_key_to_use: secret_source = "Secret Manager"; logger.info("Successfully fetched API key Secret Manager")
                else: logger.critical(f"FATAL Failed fetch API key Secret Manager {secret_name_var}"); sys.exit(1)
            except Exception as sm_err: logger.critical(f"FATAL Error Secret Manager access {sm_err}", exc_info=args.debug); sys.exit(1)
        elif direct_key_var:
            logger.info("Using API key MCP AGENT API KEY environment variable"); api_key_to_use = direct_key_var; secret_source = "Environment Variable"
        else: logger.critical("FATAL require api key flag set but neither secret name nor direct key env var set"); sys.exit(1)
        logger.info(f"API Key Authentication Enabled Source {secret_source}")
    elif args.port.lower() != "stdio": logger.info("API Key Authentication Disabled")
    # --- End API Key Handling ---

    # --- Pre flight Check GCP Clients Add Firestore ---
    try:
        logger.info("Performing pre flight GCP client initialization check")
        clients_to_init = []
        if "storage" in enabled_tools: clients_to_init.append(get_storage_client)
        if "bigquery" in enabled_tools:
             clients_to_init.append(get_bq_client)
             # Add Firestore check if BQ enabled
             clients_to_init.append(_firestore_job_store._get_db) # Use internal method force init
        if args.port.lower() != "stdio" and args.require_api_key and os.getenv('MCP_AGENT_API_KEY_SECRET_NAME'):
             clients_to_init.append(get_secret_manager_client)
        # Run initializations sequentially allow easier debug failure
        for init_func in clients_to_init:
            if asyncio.iscoroutinefunction(init_func): asyncio.run(init_func()) # Run async init checks synchronously startup
            else: init_func()
        logger.info("GCP client pre flight check successful")
    except Exception as e:
        logger.critical("FATAL GCP client check failed", extra={"error": str(e)}, exc_info=args.debug)
        logger.critical("Check ADC credentials API enablement GCS BQ Firestore SecretManager network IAM roles Firestore User Admin")
        sys.exit(1)
    # --- End Pre flight Check ---

    # --- Start Server ---
    loop = asyncio.get_event_loop(); main_task = None
    server_mode = "STDIO" if args.port.lower() == "stdio" else f"SSE on {args.host}:{args.port}"
    try:
        if args.port.lower() == "stdio":
            if args.require_api_key: logger.warning("API key requirement ignored stdio mode")
            logger.info(f"Starting server {server_mode} mode")
            main_task = loop.create_task(run_stdio_server(enabled_tools))
        else: # SSE Mode
            try:
                port_num = int(args.port); # ... validate port range ...
                if not (1024 <= port_num <= 65535): raise ValueError("Port out range")
                logger.info(f"Starting server {server_mode} mode")
                main_task = loop.create_task(run_sse_server(enabled_tools, args.host, port_num, api_key_to_use))
            except ValueError as e: logger.critical(f"Invalid port {args.port} {e}"); sys.exit(1)
        if main_task: loop.run_until_complete(main_task)
    except KeyboardInterrupt: logger.info("Server interrupted Ctrl C Shutting down")
    except Exception as e: logger.critical(f"Unexpected error running server {e}", exc_info=args.debug)
    finally: logger.info("Server shutdown process complete"); sys.exit(0) # Explicit exit

if __name__ == "__main__":
    main()
