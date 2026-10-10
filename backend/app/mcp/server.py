import logging
import sys
from pathlib import Path
from typing import Optional
from mcp.server.fastmcp import FastMCP

# Ensure backend root directory is on sys.path so 'app' is resolvable
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.mcp.tools import register_mcp_tools

# Configure root logging to output ONLY to stderr to prevent stdout protocol corruption
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("zerodha_mcp_server")


def create_mcp_server(
    session_factory=None,
    market_data_service=None,
    news_service=None,
    ai_provider=None,
    ai_reasoning_service_factory=None,
) -> FastMCP:
    """
    Factory function creating an initialized, governed FastMCP server instance.
    Registers exactly the eight approved read-only financial intelligence tools.
    """
    server = FastMCP(
        name="zerodha-ai-intelligence",
        instructions=(
            "Governed financial intelligence MCP server providing strictly read-only tools "
            "for portfolio lookup, market data snapshots, simulated news, portfolio analytics, "
            "risk assessment scoring, structured evidence bundling, and grounded AI insights. "
            "Mutating operations, trading, and system access are strictly forbidden."
        ),
        log_level="INFO",
    )

    register_mcp_tools(
        server=server,
        session_factory=session_factory,
        market_data_service=market_data_service,
        news_service=news_service,
        ai_provider=ai_provider,
        ai_reasoning_service_factory=ai_reasoning_service_factory,
    )

    return server


_global_server: Optional[FastMCP] = None


def get_mcp_server() -> FastMCP:
    """
    Lazy singleton provider for the MCP server.
    Safe to import without starting any event loop or HTTP listeners.
    """
    global _global_server
    if _global_server is None:
        _global_server = create_mcp_server()
    return _global_server


def main() -> None:
    """
    Entry point for running the governed MCP server over standard input/output (stdio).
    Stdout is strictly reserved for JSON-RPC MCP messages.
    Diagnostics and audit logs are emitted exclusively to stderr.
    """
    logger.info("Initializing Zerodha AI Intelligence MCP stdio server...")
    server = get_mcp_server()
    logger.info("Starting stdio transport loop (listening on stdin, replying on stdout)...")
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
