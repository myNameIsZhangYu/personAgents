import asyncio
import json
import signal
import sys
from pathlib import Path

import structlog
import typer
from rich.console import Console

from person_agents import __version__
from person_agents.config.settings import settings
from person_agents.llm.fallback import LLMFallbackError
from person_agents.observability.cost import CostTracker
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
def eval(
    output: str = typer.Option("", help="Write the JSON evaluation report to this path."),
) -> None:
    """Run the baseline LLM evaluation suite and print a JSON report."""
    setup_logging()
    from person_agents.eval.cases.baseline import BASELINE_CASES
    from person_agents.eval.runner import EvalRunner

    async def _eval():
        report = await EvalRunner().run_all(BASELINE_CASES)
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        console.print(rendered)
        if output:
            Path(output).write_text(rendered + "\n", encoding="utf-8")

    asyncio.run(_eval())


@app.command()
def run(
    prompt: str = typer.Argument(..., help="User prompt"),
    system: str = typer.Option("You are a helpful personal assistant.", help="System prompt"),
) -> None:
    """Send a prompt through the LLM fallback chain."""
    setup_logging()
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    CostTracker(session_id="cli-session")

    async def _run():
        from person_agents.graph.engine import run_graph
        result = await run_graph(prompt, session_id="cli-run")
        final_output = result.get("tool_results", [{}])[-1].get("output", "") if result.get("tool_results") else ""
        if final_output:
            console.print(final_output)
        else:
            console.print("[dim]Task completed.[/dim]")

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
        from person_agents.graph.engine import run_graph

        while True:
            try:
                user_input = await asyncio.to_thread(console.input, "[bold blue]> [/bold blue]")
                if not user_input.strip():
                    continue
                result = await run_graph(user_input, session_id="cli-chat")
                final_output = result.get("tool_results", [{}])[-1].get("output", "") if result.get("tool_results") else ""
                if final_output:
                    console.print(final_output)
            except KeyboardInterrupt:
                console.print(f"\n[dim]session: {tracker.total_calls} calls, {tracker.total_tokens} tokens[/dim]")
                break
            except LLMFallbackError as exc:
                console.print(f"[red]Error:[/red] {exc}")

    asyncio.run(_chat())


if __name__ == "__main__":
    app()
