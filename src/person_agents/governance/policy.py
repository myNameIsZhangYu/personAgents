import re
from enum import StrEnum

import structlog

logger = structlog.get_logger()

DANGEROUS_PATTERNS = [
    r"rm\s+(-\w*r\w*f|-\w*f\w*r|-\w*r\s+-\w*f|-\w*f\s+-\w*r)\s+[/~]",
    r"mkfs",
    r"dd\s+if=/dev/(zero|random)",
    r"\bshutdown\b",
    r"\breboot\b",
    r"git\s+push\s+(-f\b|--force)",
    r"git\s+reset\s+--hard",
    r"drop\s+(database|table)",
    r":\(\)\s*\{.*\};:",
]


class Permission(StrEnum):
    READ = "read"
    WRITE = "write"
    SHELL = "shell"
    NETWORK = "network"


class PolicyEngine:
    def __init__(self) -> None:
        self._granted: set[Permission] = {Permission.READ}

    def grant(self, permission: Permission) -> None:
        self._granted.add(permission)

    def revoke(self, permission: Permission) -> None:
        self._granted.discard(permission)

    def check(self, permission: Permission) -> bool:
        return permission in self._granted

    def check_command(self, command: str) -> tuple[bool, str]:
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Blocked dangerous pattern: {pattern}"
        return True, ""
