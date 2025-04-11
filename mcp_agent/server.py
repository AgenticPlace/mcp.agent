import asyncio
import logging
from typing import Any, Dict, List, Optional, Set

from mcp import types as mcp_types
from mcp.server import lowlevel as mcp_server
from mcp.server.models import InitializationOptions, ServerCapabilities, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.server.sse import sse_server, SseConfig

from .context import ConnectionContextManager
from .gcp_tools import ALL_TOOLS_MAP, GCS_TOOLS_SCHEMAS, BQ_TOOLS_SCHEMAS
from .utils import format_error

logger = logging.getLogger(__name__)

class McpAgentServer:
    """Wraps the MCP server logic and state."""

    def __init__(self, enabled_tools: Set[str]):
        self.enabled_tools = enabled_tools # {'storage', 'bigquery'}
        self.context_manager = ConnectionContextManager()
        self.server = mcp_server.Server("mcp-gcp-agent")

        # Assign handlers
        self.server.handle_list_tools()(self.list_tools)
        self.server.handle_call_tool()(self.call_tool)
        self.server.handle_on_disconnect()(self.on_disconnect)
        # self.server.handle_on_connect()(self.on_connect) # Optional

        # Build available tool schemas based on enabled tools
        self.available_schemas = []
        if "storage" in self.enabled_tools:
            self.available_schemas.extend(GCS_TOOLS_SCHEMAS)
        if "bigquery" in self.enabled_tools:
             self.available_schemas.extend(BQ_TOOLS_SCHEMAS)

        logger.info(f"McpAgentServer initialized. Enabled tools: {enabled_tools}")
        logger.info(f"Available MCP tool schemas: {[s.name for s in self.available_schemas]}")


    async def list_tools(self) -> List[mcp_types.Tool]:
        """Handles the list_tools MCP request."""
        logger.debug("Handling list_tools request.")
        return self.available_schemas

    async def call_tool(
        self, name: str, arguments: Dict[str, Any], conn_id: str, **kwargs # MCP passes connection ID
    ) -> List[mcp_types.TextContent | mcp_types.ImageContent | mcp_types.EmbeddedResource]:
        """Handles the call_tool MCP request."""
        logger.info(f"[Conn: {conn_id}] Handling call_tool request for tool '{name}' with args: {arguments}")

        tool_function = ALL_TOOLS_MAP.get(name)

        # Check if the tool exists and corresponds to an enabled service
        is_storage_tool = name.startswith("gcs_")
        is_bigquery_tool = name.startswith("bq_")

        if not tool_function:
            logger.warning(f"[Conn: {conn_id}] Tool '{name}' not found.")
            return format_error(f"Tool '{name}' not implemented.")

        if is_storage_tool and "storage" not in self.enabled_tools:
             logger.warning(f"[Conn: {conn_id}] Tool '{name}' requires 'storage' service, which is not enabled.")
             return format_error(f"Tool '{name}' requires the 'storage' service, which was not enabled for this server.")
        if is_bigquery_tool and "bigquery" not in self.enabled_tools:
             logger.warning(f"[Conn: {conn_id}] Tool '{name}' requires 'bigquery' service, which is not enabled.")
             return format_error(f"Tool '{name}' requires the 'bigquery' service, which was not enabled for this server.")

        try:
            # Call the actual tool implementation
            result = await tool_function(
                arguments=arguments, conn_id=conn_id, context_manager=self.context_manager
            )
            logger.info(f"[Conn: {conn_id}] Tool '{name}' executed successfully.")
            return result
        except Exception as e:
            logger.error(f"[Conn: {conn_id}] Unexpected error calling tool '{name}': {e}", exc_info=True)
            # Use the standard formatter to ensure consistent response structure
            from .utils import handle_gcp_error # Local import to avoid circular dependency if utils imports server
            return handle_gcp_error(e, f"executing tool '{name}' internally")


    # Optional: Handle connection events if needed
    # async def on_connect(self, conn_id: str):
    #     logger.info(f"[Conn: {conn_id}] Client connected.")

    async def on_disconnect(self, conn_id: str):
        """Handles client disconnects to clean up context."""
        logger.info(f"[Conn: {conn_id}] Client disconnected. Cleaning up context.")
        await self.context_manager.clear_connection_context(conn_id)

    async def run(self, read_stream, write_stream):
        """Runs the main MCP server loop."""
        init_options = InitializationOptions(
            server_name=self.server.name,
            server_version="0.1.0",
            capabilities=ServerCapabilities( # Basic capabilities
                 notification_options=NotificationOptions(),
                 experimental_capabilities={}
            )
        )
        await self.server.run(read_stream, write_stream, init_options)


async def run_stdio_server(enabled_tools: Set[str]):
    """Starts the MCP agent server communicating over standard I/O."""
    logger.info("Starting MCP Agent Server on STDIO...")
    agent_server = McpAgentServer(enabled_tools)
    try:
        async with stdio_server() as (reader, writer):
            logger.info("Stdio transport established. Running server...")
            await agent_server.run(reader, writer)
    except Exception as e:
         logger.error(f"Stdio server failed: {e}", exc_info=True)
    finally:
        logger.info("Stdio server finished.")


async def run_sse_server(enabled_tools: Set[str], host: str, port: int, api_key: Optional[str] = None):
    """Starts the MCP agent server communicating over Server-Sent Events (SSE)."""
    logger.info(f"Starting MCP Agent Server on SSE (http://{host}:{port}/mcp)...")
    agent_server = McpAgentServer(enabled_tools)

    auth_handler = None
    if api_key:
        logger.info("API key authentication enabled for SSE.")
        async def check_auth(headers: Dict[str, str]) -> bool:
            auth_header = headers.get("authorization", "")
            expected = f"Bearer {api_key}"
            if auth_header == expected:
                return True
            logger.warning(f"SSE authentication failed. Received: '{auth_header[:15]}...'")
            return False
        auth_handler = check_auth

    sse_config = SseConfig(host=host, port=port, endpoint="/mcp", auth_handler=auth_handler)

    try:
        async with sse_server(sse_config) as (reader, writer):
             logger.info("SSE transport established. Running server...")
             await agent_server.run(reader, writer)
    except OSError as e:
         if "address already in use" in str(e).lower():
              logger.error(f"Failed to start SSE server: Address http://{host}:{port} already in use.")
         else:
              logger.error(f"SSE server failed with OS error: {e}", exc_info=True)
    except Exception as e:
         logger.error(f"SSE server failed: {e}", exc_info=True)
    finally:
         logger.info("SSE server finished.")
