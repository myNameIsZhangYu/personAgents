import asyncio
import signal
import sys

import structlog
import typer
from rich.console import Console

from person_agents import __version__
from person_agents.config.settings import settings
from person_agents.llm.fallback import LLMFallbackError, call_with_fallback
from person_agents.observability.cost import CostTracker
from person_agents.observability.langfuse import trace_llm_call
from person_agents.observability.logging import setup_logging

app = typer.Typer(name="person-agents", help="Personal agent CLI")
console = Console()
logger = structlog.get_logger()

def _signal_handler(sig: int, frame: object) -> None:
    logger.info("graceful_shutdown", signal=sig)
    sys.exit(0)


@app.command()
def version() -> None:
    """Show version."""
    console.print(f"person-agents v{__version__}")


@app.command()
def doctor() -> None:
    """Check system health: config, LLM API, Ollama, directories."""
    setup_logging()
    checks: list[tuple[str, bool, str]] = []

    checks.append(("OpenAI API key", bool(settings.openai_api_key), "not set" if not settings.openai_api_key else "ok"))
    checks.append(("Data directory", settings.data_dir.exists(), str(settings.data_dir)))
    checks.append(("SQLite path writable", _check_write(settings.sqlite_path.parent), str(settings.sqlite_path)))

    try:
        import httpx
        resp = httpx.get(settings.ollama_base_url + "/api/tags", timeout=3)
        checks.append(("Ollama", resp.status_code == 200, settings.ollama_base_url))
    except httpx.HTTPError:
        checks.append(("Ollama", False, "unreachable"))

    for name, ok, detail in checks:
        status = "[green]✓[/green]" if ok else "[red]✗[/red]"
        console.print(f"  {status} {name}: {detail}")


def _check_write(path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".write_test"
        test_file.touch()
        test_file.unlink()
        return True
    except OSError:
        return False


@app.command()
def run(
    prompt: str = typer.Argument(..., help="User prompt"),
    system: str = typer.Option("You are a helpful personal assistant.", help="System prompt"),
) -> None:
    """Send a prompt through the LLM fallback chain."""
    setup_logging()
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    tracker = CostTracker(session_id="cli-session")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]

    async def _run():
        try:
            resp = await call_with_fallback(messages)
            tracker.record(resp.model, resp.prompt_tokens, resp.completion_tokens, 0)
            trace_llm_call(
                "cli-run", resp.model, resp.prompt_tokens, resp.completion_tokens, 0,
                messages=messages, output=resp.content, degraded=resp.degraded,
            )
            console.print(resp.content)
            logger.info("llm_complete", model=resp.model, degraded=resp.degraded, total_tokens=tracker.total_tokens)
        except LLMFallbackError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    asyncio.run(_run())


@app.command()
def chat() -> None:
    """Interactive chat loop."""
    setup_logging()
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    console.print("[bold]person-agents chat[/bold] (Ctrl+C to exit)")
    tracker = CostTracker(session_id="chat-session")

    async def _chat() -> None:
        from person_agents.graph.nodes import executor_node, intent_node

        while True:
            try:
                user_input = await asyncio.to_thread(console.input, "[bold blue]> [/bold blue]")
                if not user_input.strip():
                    continue
                state = {"messages": [{"role": "user", "content": user_input}], "intent": "", "plan": [], "current_step": 0, "tool_results": [], "critic_feedback": "", "memory_context": [], "status": "", "degraded": False, "error": None}
                result = await intent_node(state)
                state.update(result)
                if state["intent"] in ("chat", "task", "tool_use"):
                    result = await executor_node(state)
                    state.update(result)
                    for r in state["tool_results"]:
                        console.print(r["output"])
                        tracker.record("agent", 0, 0, 0)
                else:
                    messages = [{"role": "user", "content": user_input}]
                    resp = await call_with_fallback(messages)
                    tracker.record(resp.model, resp.prompt_tokens, resp.completion_tokens, 0)
                    console.print(resp.content)
                trace_llm_call("cli-chat", "agent", 0, 0, 0)
            except KeyboardInterrupt:
                console.print(f"\n[dim]session: {tracker.total_calls} calls, {tracker.total_tokens} tokens[/dim]")
                break
            except LLMFallbackError as exc:
                console.print(f"[red]Error:[/red] {exc}")

    asyncio.run(_chat())


if __name__ == "__main__":
    app()
