"""
Run the agentic investigation against the healthcare RPM dataset.

Interactive (just run it, then type your question at the prompt):
    python demos/healthcare_rpm/run.py

One-shot (pass the question directly, runs once and exits):
    python demos/healthcare_rpm/run.py --goal "Which COPD patients look unstable?"
"""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402

from demos.healthcare_rpm.config import DEFAULT_GOAL, EXAMPLES, SCHEMA  # noqa: E402
from src.core.agent import investigate  # noqa: E402
from src.core.db import get_client  # noqa: E402

console = Console()


def _dataset_size(client):
    try:
        return client.query("SELECT count() FROM vitals").result_rows[0][0]
    except Exception:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goal", default=None,
                    help="Ask one question and exit. Omit this to go interactive.")
    args = ap.parse_args()

    client = get_client()
    n = _dataset_size(client)
    if not n:
        print("No data found. Run:  python demos/healthcare_rpm/generate_data.py")
        sys.exit(1)

    # one-shot mode
    if args.goal:
        investigate(args.goal, SCHEMA)
        return

    # interactive mode
    examples = "\n".join(f"  [green]>[/green] {e}" for e in EXAMPLES)
    console.print(
        Panel(
            f"[bold]Healthcare RPM Agent[/bold]   [dim]ClickHouse + Agentic AI[/dim]\n"
            f"Dataset: [bold cyan]{n:,}[/bold cyan] vitals rows\n\n"
            f"[dim]Ask anything about the patient data. For example:[/dim]\n{examples}\n\n"
            f"[dim]Enter a blank line for the default question, or type 'q' to quit.[/dim]",
            border_style="cyan", title_align="left",
        )
    )

    while True:
        try:
            goal = console.input("\n[bold cyan]Question[/bold cyan] [dim](q to quit)[/dim]: ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("bye.")
            break
        if goal.lower() in ("q", "quit", "exit"):
            console.print("bye.")
            break
        if not goal:
            goal = DEFAULT_GOAL
            console.print("[dim]Using default question.[/dim]")
        investigate(goal, SCHEMA)


if __name__ == "__main__":
    main()
