"""
Zerodha AI Intelligence Platform - Governed Model Context Protocol (MCP) Package.

Exposes strictly read-only financial tools for portfolio lookup, market data,
news, analytics, risk scoring, and evidence bundle aggregation over stdio transport.
"""

from app.mcp.schemas import APPROVED_TOOLS, MCPErrorCode

__all__ = [
    "APPROVED_TOOLS",
    "MCPErrorCode",
]
