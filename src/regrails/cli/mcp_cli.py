"""``regrails mcp`` sub-app — run the MCP server."""

from __future__ import annotations

import typer

from ..mcp_server import serve

app = typer.Typer(help="Run the RegRails MCP server (guardrail as agent tools).", no_args_is_help=True)


@app.command("serve")
def serve_cmd() -> None:
    """Start the MCP server over stdio, exposing the guardrail as agent-callable tools."""
    serve()
