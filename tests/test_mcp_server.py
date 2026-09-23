"""Tool registration and dispatch through FastMCP.

The tools are registered natively, so FastMCP's own ``tools/list`` and
``tools/call`` handlers serve them and ``MCPTool.run`` owns argument
validation, error translation, and serialization. These tests drive
the server through a real client session.
"""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastmcp import Client

from courtlistener.exceptions import CourtListenerAPIError
from courtlistener.mcp.server import create_mcp_server
from courtlistener.mcp.tools import MCP_TOOLS
from courtlistener.mcp.tools.get_counts_tool import GetCountsTool

pytestmark = pytest.mark.asyncio


def _api_error(status_code: int, detail) -> CourtListenerAPIError:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    return CourtListenerAPIError(status_code, detail, response)


async def _call(name: str, arguments: dict):
    async with Client(create_mcp_server()) as client:
        return await client.call_tool(name, arguments, raise_on_error=False)


class TestListTools:
    async def test_lists_the_registry_unchanged(self):
        async with Client(create_mcp_server()) as client:
            listed = await client.list_tools()

        assert [tool.name for tool in listed] == list(MCP_TOOLS)
        for tool in listed:
            registered = MCP_TOOLS[tool.name]
            assert tool.inputSchema == registered.get_input_schema()
            assert tool.description == type(registered).__doc__
            assert tool.annotations == registered.annotations
            assert tool.title == registered.annotations.title


class TestCallTool:
    async def test_returns_the_tool_result_as_json_text(self):
        result = await _call("get_endpoint_schema", {"endpoint_id": "dockets"})

        assert result.is_error is False
        schema = json.loads(result.content[0].text)
        assert "court" in schema["properties"]

    async def test_validates_arguments_against_the_published_schema(self):
        result = await _call("get_endpoint_schema", {"endpoint": "dockets"})

        assert result.is_error
        text = result.content[0].text
        assert "Invalid arguments for tool 'get_endpoint_schema'" in text
        assert "'endpoint' was unexpected" in text

    async def test_explicit_null_reaches_the_tool_as_unset(self):
        result = await _call(
            "extract_citations",
            {"text": "See Brown v. Board, 347 U.S. 483.", "resolve": None},
        )

        assert result.is_error is False
        assert "347 U.S. 483" in result.content[0].text

    async def test_typed_tool_errors_reach_the_client_unmasked(self):
        error = _api_error(429, {"detail": "Request was throttled."})
        with patch.object(GetCountsTool, "call", side_effect=error):
            result = await _call("get_counts", {"query_id": "abc12345"})

        assert result.is_error
        assert result.content[0].text.startswith("Rate limit exceeded")
        assert "get_api_usage" in result.content[0].text

    async def test_unexpected_exceptions_are_wrapped_by_fastmcp(self):
        with patch.object(GetCountsTool, "call", side_effect=ValueError("x")):
            result = await _call("get_counts", {"query_id": "abc12345"})

        assert result.is_error
        assert result.content[0].text == "Error calling tool 'get_counts': x"

    async def test_unknown_tool_is_reported(self):
        result = await _call("no_such_tool", {})

        assert result.is_error
        assert "Unknown tool" in result.content[0].text
