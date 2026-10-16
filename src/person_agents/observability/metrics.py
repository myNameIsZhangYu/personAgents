
from prometheus_client import CollectorRegistry, Counter, Histogram

registry = CollectorRegistry()

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
    registry=registry,
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    registry=registry,
)
run_jobs_total = Counter(
    "run_jobs_total",
    "Run job lifecycle events",
    ["status"],
    registry=registry,
)
tool_calls_total = Counter(
    "tool_calls_total",
    "Governed tool calls",
    ["tool", "status"],
    registry=registry,
)
llm_calls_total = Counter(
    "llm_calls_total",
    "Governed LLM calls",
    ["status", "degraded"],
    registry=registry,
)
