from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class CostEntry:
    timestamp: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


@dataclass
class CostTracker:
    session_id: str
    entries: list[CostEntry] = field(default_factory=list)

    def record(self, model: str, prompt_tokens: int, completion_tokens: int, latency_ms: int) -> None:
        self.entries.append(
            CostEntry(
                timestamp=datetime.now(UTC).isoformat(),
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
            )
        )

    @property
    def total_tokens(self) -> int:
        return sum(e.prompt_tokens + e.completion_tokens for e in self.entries)

    @property
    def total_calls(self) -> int:
        return len(self.entries)
