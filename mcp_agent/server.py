import asyncio
import json
import logging
import sys
from typing import Set, Optional, Any, Dict, List, Callable, Awaitable

from aiohttp import web
from aiohttp_sse import sse_response
from mcp import types as mcp_types

# Attempt to import ALL_TOOLS_MAP and FirestoreBqJobStore
try:
    from .gcp_tools import ALL_TOOLS_MAP # To be populated later
    from .job_store import FirestoreBqJobStore # Now available
except ImportError:
    # This implies a packaging or setup issue if job_store is not found.
    logger = logging.getLogger("mcp_agent.server_prelim") # Use a distinct logger name for this specific warning
    logger.critical("Could not import ALL_TOOLS_MAP or FirestoreBqJobStore. Tool dispatch will be severely limited or non-functional.", exc_info=True)
    ALL_TOOLS_MAP: Dict[str, Callable[..., Awaitable[List[mcp_types.Content]]]] = {}
    FirestoreBqJobStore = None # Make it None if not imported, so type hints don't break entirely below

logger = logging.getLogger("mcp_agent.server") # Main logger for this module

# --- Tool Dispatcher ---
async def dispatch_tool(
    message: Dict[str, Any],
    enabled_tools: Set[str], # Currently unused here, logic might be in ALL_TOOLS_MAP population
    conn_id: str,
    bq_job_store: Optional[FirestoreBqJobStore] = None,
    **kwargs: Any # To catch any other args passed from server handlers
) -> List[mcp_types.Content]:
    """
    Dispatches an MCP tool call to the appropriate implementation.
    """
    tool_name = message.get("tool_name")
    arguments = message.get("arguments", {})

    if not tool_name:
        logger.warning("Request missing 'tool_name'.", extra={"conn_id": conn_id, "request_message": message})
        return [mcp_types.TextContent(type="text", text=json.dumps({"status": "error", "message": "Missing tool_name in request."}))]

    if not ALL_TOOLS_MAP: # Check if tool map is empty (e.g. import failed)
        logger.error("ALL_TOOLS_MAP is empty. Cannot dispatch any tools.", extra={"conn_id": conn_id})
        return [mcp_types.TextContent(type="text", text=json.dumps({"status": "error", "message": "Tool dispatch mechanism not available."}))]

    if tool_name not in ALL_TOOLS_MAP:
        logger.warning(f"Tool '{tool_name}' not recognized or not enabled.", extra={"conn_id": conn_id, "tool_name": tool_name})
        return [mcp_types.TextContent(type="text", text=json.dumps({"status": "error", "message": f"Tool '{tool_name}' not recognized or not enabled."}))]

    tool_function = ALL_TOOLS_MAP[tool_name]
    logger.info(f"Dispatching to tool: '{tool_name}'", extra={"conn_id": conn_id, "tool_name": tool_name, "arguments": arguments})

    try:
        # Pass bq_job_store to the tool function if it's available and the tool might need it.
        # Individual tools will need to be designed to accept bq_job_store in their **kwargs or explicitly.
        # For now, we pass it if it's not None.
        if bq_job_store:
            response_contents = await tool_function(arguments=arguments, conn_id=conn_id, bq_job_store=bq_job_store, **kwargs)
        else:
            response_contents = await tool_function(arguments=arguments, conn_id=conn_id, **kwargs)
        return response_contents
    except Exception as e:
        logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True, extra={"conn_id": conn_id, "tool_name": tool_name})
        # Consider using handle_gcp_error from utils if it's a GCP exception
        return [mcp_types.TextContent(type="text", text=json.dumps({"status": "error", "message": f"Error executing tool '{tool_name}': {str(e)}"}))]


# --- STDIO Server Implementation ---
async def run_stdio_server(
    enabled_tools: Set[str],
    bq_job_store: Optional[FirestoreBqJobStore] = None,
    **kwargs: Any # Catch-all for future parameters
) -> None:
    logger.info("Starting STDIO server. Listening on stdin...")
    # For STDIO, conn_id might be less dynamic unless specified by client in messages.
    # Using a fixed one for the session.
    conn_id = "stdio_session_main"

    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                logger.info("STDIN closed. Shutting down STDIO server.")
                break
            line = line.strip()
            if not line:
                continue

            logger.debug(f"Received STDIO message: {line}", extra={"conn_id": conn_id})
            try:
                message = json.loads(line)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from STDIO: {line}. Error: {e}", exc_info=True, extra={"conn_id": conn_id})
                error_response_obj = mcp_types.TextContent(type="text", text=json.dumps({"status": "error", "message": "Invalid JSON message received."}))
                sys.stdout.write(json.dumps(error_response_obj.model_dump()) + "\n")
                sys.stdout.flush()
                continue

            response_contents = await dispatch_tool(
                message=message,
                enabled_tools=enabled_tools,
                conn_id=conn_id,
                bq_job_store=bq_job_store
            )

            for content in response_contents:
                if isinstance(content, mcp_types.Content):
                    sys.stdout.write(json.dumps(content.model_dump()) + "\n")
                else: # Should not happen if dispatch_tool returns List[mcp_types.Content]
                    logger.error(f"Invalid content type from dispatch_tool: {type(content)}", extra={"conn_id": conn_id})
                    sys.stdout.write(json.dumps(str(content)) + "\n") # Best effort
            sys.stdout.flush()

        except KeyboardInterrupt:
            logger.info("STDIO server interrupted by user (Ctrl+C).")
            break
        except Exception as e:
            logger.critical(f"Unexpected error in STDIO server loop: {e}", exc_info=True, extra={"conn_id": conn_id})
            await asyncio.sleep(1)

    logger.info("STDIO server has shut down.")


# --- SSE Server Implementation ---
@web.middleware
async def api_key_middleware(request: web.Request, handler: Callable):
    api_key_required = request.app.get("api_key")
    # This middleware is only active if api_key_required is not None in app state
    if api_key_required:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("SSE request missing or malformed Authorization header.", extra={"remote": request.remote})
            raise web.HTTPUnauthorized(
                text=json.dumps({"status": "error", "message": "Missing or malformed Authorization header. Expected 'Bearer <API_KEY>'."}),
                content_type="application/json"
            )

        token = auth_header.split("Bearer ")[1]
        if token != api_key_required:
            logger.warning("SSE request with invalid API key.", extra={"remote": request.remote})
            raise web.HTTPForbidden(
                text=json.dumps({"status": "error", "message": "Invalid API key."}),
                content_type="application/json"
            )
    return await handler(request)

async def handle_mcp_sse_request(request: web.Request):
    # Generate a somewhat unique connection ID for logging/tracing this request
    conn_id = request.headers.get("X-Connection-ID") # Allow client to specify
    if not conn_id:
        conn_id = f"sse_{request.remote}_{int(asyncio.get_running_loop().time())}"

    logger.info(f"SSE request received from {request.remote}", extra={"conn_id": conn_id, "path": request.path, "headers": dict(request.headers)})

    if request.content_type != 'application/json':
        logger.warning(f"Invalid content type: {request.content_type}", extra={"conn_id": conn_id})
        raise web.HTTPUnsupportedMediaType(
            text=json.dumps({"status": "error", "message": "Expected application/json content type."}),
            content_type="application/json"
        )

    try:
        message = await request.json()
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from SSE request: {e}", exc_info=True, extra={"conn_id": conn_id})
        raise web.HTTPBadRequest(
            text=json.dumps({"status": "error", "message": f"Invalid JSON in request body: {e}"}),
            content_type="application/json"
        )

    logger.debug(f"Parsed SSE message: {message}", extra={"conn_id": conn_id})

    enabled_tools = request.app["enabled_tools"]
    bq_job_store = request.app.get("bq_job_store") # Will be None if BQ not enabled

    response_contents = await dispatch_tool(
        message=message,
        enabled_tools=enabled_tools,
        conn_id=conn_id,
        bq_job_store=bq_job_store
    )

    # Prepare SSE response. Each Content object becomes a separate event.
    # The MCP spec usually expects a stream of JSON objects.
    # aiohttp-sse sends events in the format:
    # event: <event_name>
    # data: <json_string_payload>
    # id: <optional_id>
    # We'll use the default event name 'message'.
    async with sse_response(request) as sse_resp:
        for content_idx, content_obj in enumerate(response_contents):
            try:
                if isinstance(content_obj, mcp_types.Content):
                    payload_str = json.dumps(content_obj.model_dump())
                else: # Should ideally not happen
                    logger.error(f"dispatch_tool returned non-Content item: {type(content_obj)}", extra={"conn_id": conn_id})
                    payload_str = json.dumps(str(content_obj)) # Best effort

                await sse_resp.send(payload_str) # Default event name is 'message'
                logger.debug(f"Sent SSE event {content_idx + 1}/{len(response_contents)}: {payload_str[:100]}...", extra={"conn_id": conn_id})
            except Exception as e:
                logger.error(f"Error serializing or sending SSE event {content_idx}: {e}", exc_info=True, extra={"conn_id": conn_id})
                # Attempt to send an error event back to the client if the stream is still open
                try:
                    error_event_payload = json.dumps({"status": "error", "message": f"Internal error during SSE event generation for event {content_idx}: {str(e)}"})
                    await sse_resp.send(error_event_payload)
                except Exception as send_err_exc:
                    logger.error(f"Failed to send error event back to client: {send_err_exc}", extra={"conn_id": conn_id})
                    # At this point, the connection might be too broken to continue.
                    # The sse_response context manager will handle closing.
                    break
    return sse_resp # Return the response object


async def run_sse_server(
    enabled_tools: Set[str],
    host: str,
    port: int,
    api_key: Optional[str], # This is the API key value itself, if configured
    bq_job_store: Optional[FirestoreBqJobStore] = None,
    **kwargs: Any # Catch-all for future parameters
) -> None:
    # If api_key is provided, authentication is active.
    # The middleware will use app["api_key"] to check against.
    app = web.Application(middlewares=[api_key_middleware] if api_key else [])

    app["enabled_tools"] = enabled_tools
    app["api_key"] = api_key # Store the actual API key string for the middleware to use. Could be None.
    app["bq_job_store"] = bq_job_store

    if api_key:
        logger.info(f"SSE Server configured WITH API Key Authentication.")
    else:
        logger.info(f"SSE Server configured WITHOUT API Key Authentication (no API key provided or --require-api-key not used).")

    app.router.add_post("/mcp", handle_mcp_sse_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)

    logger.info(f"Starting SSE server on http://{host}:{port}/mcp")
    try:
        await site.start()
        # Keep server running until interrupted
        while True:
            await asyncio.Future() # Wait indefinitely until cancelled
    except KeyboardInterrupt:
        logger.info("SSE server interrupted by user (Ctrl+C).")
    except Exception as e:
        logger.critical(f"SSE server failed: {e}", exc_info=True)
    finally:
        logger.info("Shutting down SSE server...")
        await runner.cleanup()
        logger.info("SSE server has shut down.")
