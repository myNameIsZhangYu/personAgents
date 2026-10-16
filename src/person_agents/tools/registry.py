from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import structlog

from person_agents.tools.mcp_filesystem import MCPFilesystemTool

logger = structlog.get_logger()


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Awaitable[Any]]
    requires_confirm: bool = False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}

    def register(self, tool: ToolDef) -> None:
        self._tools[tool.name] = tool
        logger.info("tool_registered", tool=tool.name)

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDef]:
        return list(self._tools.values())

    def to_openai_schema(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]


def register_default_tools(registry: ToolRegistry, workspace_root: str = "/tmp/person-agents-workspace") -> None:
    fs = MCPFilesystemTool(root_dir=workspace_root)

    async def fs_handler(arguments: dict) -> dict:
        return await fs.call(arguments)

    registry.register(ToolDef(
        name="filesystem",
        description="Read, write, list, or delete files in a sandboxed workspace directory",
        parameters={
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["read", "write", "list", "delete"]},
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["operation", "path"],
        },
        handler=fs_handler,
        requires_confirm=True,
    ))
