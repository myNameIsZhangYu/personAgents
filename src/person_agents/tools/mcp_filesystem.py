from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


class MCPFilesystemTool:
    """MCP-compatible filesystem tool using direct file I/O.

    Provides read, write, list, and delete operations within a sandboxed root directory.
    """

    def __init__(self, root_dir: str | Path):
        self.root = Path(root_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        resolved = (self.root / path).resolve()
        if not resolved.is_relative_to(self.root):
            raise PermissionError(f"Path escapes sandbox root: {path}")
        return resolved

    async def call(self, arguments: dict[str, Any]) -> dict[str, Any]:
        operation = arguments.get("operation", "")
        path = arguments.get("path", "")
        try:
            target = self._resolve(path)
            if operation == "read":
                return {"status": "ok", "content": target.read_text(encoding="utf-8")}
            if operation == "write":
                content = arguments.get("content", "")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                return {"status": "ok", "bytes_written": len(content)}
            if operation == "list":
                if target.is_dir():
                    items = [{"name": p.name, "is_dir": p.is_dir()} for p in sorted(target.iterdir())]
                else:
                    items = [{"name": target.name, "is_dir": False}]
                return {"status": "ok", "items": items}
            if operation == "delete":
                if target.is_file():
                    target.unlink()
                elif target.is_dir():
                    import shutil
                    shutil.rmtree(target)
                return {"status": "ok"}
            return {"status": "error", "message": f"Unknown operation: {operation}"}
        except PermissionError as exc:
            return {"status": "error", "message": str(exc)}
        except FileNotFoundError:
            return {"status": "error", "message": f"Path not found: {path}"}
        except OSError as exc:
            return {"status": "error", "message": str(exc)}
