import argparse
import asyncio
import logging
import sys
from typing import Set

# Ensure utils is importable if running cli directly (might need adjustments based on execution context)
try:
    from .server import run_stdio_server, run_sse_server
except ImportError:
     # Handle case where script is run directly, adjust path if necessary
     # This is a common pattern but might need refinement based on install/run method
     import os
     sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
     from mcp_agent.server import run_stdio_server, run_sse_server


# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr, # Log to stderr so stdout/stdin can be used for MCP
)
# Get logger for this module
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="Run the MCP Agent server for GCS/BigQuery.")
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
        help="Host address to bind to for SSE server (default: 127.0.0.1). Use 0.0.0.0 for network access.",
    )
    parser.add_argument(
        "--require-api-key",
        type=str,
        default=None,
        metavar="API_KEY",
        help="[SSE Only] Require clients to send 'Authorization: Bearer <API_KEY>' header.",
    )
    parser.add_argument(
         "--debug",
         action="store_true",
         help="Enable debug logging for all loggers."
    )

    return parser.parse_args()

def main():
    args = parse_args()

    # Set logging level for all loggers if debug is enabled
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        # Example: Set google client libs to INFO to reduce verbosity unless needed
        logging.getLogger("google.cloud").setLevel(logging.INFO)
        logging.getLogger("google.api_core").setLevel(logging.INFO)
        logging.getLogger("google.auth").setLevel(logging.INFO)
        logger.debug("Debug logging enabled for mcp_agent.")


    enabled_tools: Set[str] = set(t.strip().lower() for t in args.tools.split(',') if t.strip())
    valid_tools = {"storage", "bigquery"}

    # Validate tools
    invalid_tools = enabled_tools - valid_tools
    if invalid_tools:
         logger.error(f"Invalid tool(s) specified: {', '.join(invalid_tools)}. Allowed tools: {', '.join(valid_tools)}")
         sys.exit(1)
    if not enabled_tools:
         logger.error("No tools specified. Use --tools storage,bigquery or similar.")
         sys.exit(1)

    logger.info(f"Configuring mcp-agent server...")
    logger.info(f"Enabled tools: {enabled_tools}")

    if args.port.lower() == "stdio":
        if args.require_api_key:
             logger.warning("--require-api-key is ignored for stdio mode.")
        logger.info("Mode: STDIO")
        try:
            # Ensure GCP clients can initialize before entering async loop potentially
            from .gcp_tools.storage import get_storage_client
            from .gcp_tools.bigquery import get_bq_client
            if "storage" in enabled_tools: get_storage_client()
            if "bigquery" in enabled_tools: get_bq_client()
            # Run the server
            asyncio.run(run_stdio_server(enabled_tools))
        except KeyboardInterrupt:
            logger.info("Stdio server interrupted by user.")
        except Exception as e:
             logger.critical(f"Failed to start or run stdio server: {e}", exc_info=args.debug)
             sys.exit(1)
    else:
        try:
            port_num = int(args.port)
            if not (1024 <= port_num <= 65535):
                 raise ValueError("Port number must be between 1024 and 65535.")
            logger.info(f"Mode: SSE on {args.host}:{port_num}")
            if args.require_api_key:
                 logger.info("API Key Authentication: Enabled")
            else:
                 logger.info("API Key Authentication: Disabled")

            # Ensure GCP clients can initialize before entering async loop potentially
            from .gcp_tools.storage import get_storage_client
            from .gcp_tools.bigquery import get_bq_client
            if "storage" in enabled_tools: get_storage_client()
            if "bigquery" in enabled_tools: get_bq_client()
            # Run the server
            asyncio.run(run_sse_server(enabled_tools, args.host, port_num, args.require_api_key))

        except ValueError as e:
            logger.error(f"Invalid port number specified: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
             logger.info("SSE server interrupted by user.")
        except Exception as e:
             logger.critical(f"Failed to start or run SSE server: {e}", exc_info=args.debug)
             sys.exit(1)

if __name__ == "__main__":
    main()
