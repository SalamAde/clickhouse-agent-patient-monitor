"""
Two-phase question answering over ClickHouse.

1) PLAN  - one model call writes the minimal SQL to gather the data (one script
           per distinct question, capped at 5). These scripts are what gets saved
           and is reusable.
2) ANSWER - run that SQL, then one model call writes a plain-language answer using
           the real numbers (it can explain and recommend, like an assistant).

Reuse re-runs the saved scripts live (no model calls, no tokens).

`answer(question, schema)` and `replay_scripts(scripts)` are generators that yield
events; the web app and terminal both consume them.
"""
import json
import os
import re

import anthropic
from anthropic import Anthropic
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from .db import get_client, run_query

console = Console()

CH_TIPS = """ClickHouse SQL rules (follow exactly):
- ASCII operators only (>=, <=, !=).
- No correlated subqueries (in SELECT, WHERE or ORDER BY); use JOINs or window functions.
- Alias EVERY selected column explicitly with AS, especially inside CTEs
  (e.g. SELECT p.patient_id AS patient_id, ...). The outer query must reference those
  exact alias names, unqualified.
- Prefer ONE query using conditional aggregation (avgIf, countIf, sumIf, multiIf) over
  deep chains of CTEs. Compare time windows like
  avgIf(value, event_time >= now() - INTERVAL 3 DAY) vs the earlier window."""

SYSTEM_PLAN = """You write ClickHouse SQL that gathers the data needed to answer the user's question.

Output ONLY a JSON object, with no prose and no markdown fences:
{{"scripts": [{{"title": "short label", "sql": "..."}}]}}

Rules:
- Write the MINIMAL SQL needed. Most questions need exactly ONE query.
- One query per distinct sub-question. If several questions are asked, return one
  script per question. Never return more than 5 scripts.
- The result must be EXACTLY the answer and NOTHING more. Select ONLY the column(s)
  the question asks about; do NOT add extra columns (ids, condition, region, sex,
  timestamps, helper metrics, etc.) unless the question explicitly needs them.
  Return only the rows needed: if the question implies a count ("top 5", "the
  patient who...", "how many"), use that exact LIMIT or return a single value.
  If the question does NOT specify how many rows, add LIMIT 10.
  Sort only when the question asks for a ranking. Round numbers sensibly.
- Even if the question says "explain" or "recommend", here you ONLY output the
  data-gathering SQL as JSON. The explanation is written in a later step.
{ch_tips}
- No SQL comments, no prose.

Preferred single-query pattern for comparing a recent window vs an earlier baseline
(use this shape instead of chained CTEs):
SELECT patient_id AS patient_id,
       round(avgIf(value, event_time >= now() - INTERVAL 3 DAY), 1) AS recent_avg,
       round(avgIf(value, event_time >= now() - INTERVAL 7 DAY AND event_time < now() - INTERVAL 3 DAY), 1) AS baseline_avg
FROM vitals
WHERE metric = 'spo2'
GROUP BY patient_id
ORDER BY recent_avg - baseline_avg ASC
LIMIT 20

DATABASE SCHEMA AND DOMAIN NOTES:
{schema}
"""

SYSTEM_ANSWER = (
    "You are a data analyst. Answer the user's question using ONLY the query results "
    "provided below. Every number, name, and id you mention MUST appear verbatim in "
    "those results - do not compute, estimate, round differently, or invent values, "
    "and do not mention rows that are not shown. If the results are empty, say there "
    "were no matching records. Be concise (a short paragraph or a tight bullet list); "
    "you may add a brief recommendation only if the question asks for one. "
    "No emojis, no em dashes."
)


def _model(model):
    return model or os.getenv("AGENT_MODEL", "claude-haiku-4-5-20251001")


def _strip_fences(text):
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    return t


def _cap_rows(sql, rows, cap=10):
    """If the query has no explicit LIMIT, cap returned rows (default 10)."""
    if rows and len(rows) > cap and not re.search(r"\blimit\b", sql, re.I):
        return rows[:cap]
    return rows


def _format_rows(cols, rows, limit=30):
    lines = [" | ".join(map(str, cols))]
    for row in rows[:limit]:
        lines.append(" | ".join(str(x) for x in row))
    if len(rows) > limit:
        lines.append(f"... (+{len(rows) - limit} more rows)")
    return "\n".join(lines)


def _parse_scripts(text):
    if not text:
        return None
    t = _strip_fences(text)
    obj = None
    try:
        obj = json.loads(t)
    except Exception:
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            try:
                obj = json.loads(m.group(0))
            except Exception:
                obj = None
    if isinstance(obj, dict) and isinstance(obj.get("scripts"), list):
        out = []
        for it in obj["scripts"]:
            if isinstance(it, dict) and it.get("sql"):
                title = (it.get("title") or "").strip() or "Result"
                out.append({"title": title, "sql": it["sql"].strip()})
        return out[:5] or None
    # fallback: a bare SELECT with no JSON wrapper - only if it looks complete
    if re.search(r"\bselect\b", t, re.I) and t.count("(") == t.count(")"):
        return [{"title": "Result", "sql": t}]
    return None


def generate_scripts(question, schema, model=None):
    llm = Anthropic(max_retries=5)
    system = [{"type": "text", "text": SYSTEM_PLAN.format(schema=schema, ch_tips=CH_TIPS),
               "cache_control": {"type": "ephemeral"}}]
    resp = llm.messages.create(model=_model(model), max_tokens=4000, system=system,
                               messages=[{"role": "user", "content": question}])
    text = "".join(b.text for b in resp.content if b.type == "text")
    return _parse_scripts(text) or []


def repair_sql(question, schema, sql, error, model=None):
    # Use a stronger model to actually fix it (the fast model wrote the broken one).
    repair_model = os.getenv("REPAIR_MODEL", "claude-sonnet-4-6")
    llm = Anthropic(max_retries=3)
    prompt = (
        "This ClickHouse SQL failed. Return ONLY the corrected SQL - no prose, no fences.\n\n"
        f"{CH_TIPS}\n\n"
        f"User question: {question}\n\nSchema:\n{schema}\n\nFailed SQL:\n{sql}\n\nError:\n{error}"
    )
    resp = llm.messages.create(model=repair_model, max_tokens=2500,
                               messages=[{"role": "user", "content": prompt}])
    return _strip_fences("".join(b.text for b in resp.content if b.type == "text"))


def synthesize_answer(question, results, model=None):
    llm = Anthropic(max_retries=4)
    blocks = []
    for r in results:
        if r["error"]:
            blocks.append(f"[{r['title']}] ERROR: {r['error']}")
        else:
            blocks.append(f"[{r['title']}] columns={r['cols']}\n{_format_rows(r['cols'], r['rows'])}")
    data = "\n\n".join(blocks) if blocks else "(no data)"
    msg = f"Question: {question}\n\nQuery results:\n{data}"
    resp = llm.messages.create(model=_model(model), max_tokens=700, system=SYSTEM_ANSWER,
                               messages=[{"role": "user", "content": msg}])
    return "".join(b.text for b in resp.content if b.type == "text").strip()


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
def answer(question, schema, model=None):
    """
    Yields:
      {"type": "error", "message": str}
      {"type": "query", "n": int, "title": str, "sql": str, "rows": list, "cols": list, "ms": float, "error": str|None}
      {"type": "answer", "text": str}
    """
    yield {"type": "status", "stage": "Planning the SQL..."}
    try:
        scripts = generate_scripts(question, schema, model)
    except anthropic.APIError as e:
        yield {"type": "error", "message": f"The AI service is temporarily unavailable ({e}). Please try again."}
        return
    if not scripts:
        yield {"type": "error", "message": "Could not work out how to query that. Try rephrasing."}
        return

    ch = get_client()
    results = []
    yield {"type": "status", "stage": "Running the queries..."}
    for i, spec in enumerate(scripts, 1):
        title, sql = spec["title"], spec["sql"]
        rows, cols, ms, err = [], [], 0.0, None
        try:
            rows, cols, ms = run_query(ch, sql)
        except Exception as first_err:  # noqa: BLE001 - one bounded repair
            try:
                fixed = repair_sql(question, schema, sql, str(first_err), model)
                if fixed and fixed != sql:
                    sql = fixed
                    rows, cols, ms = run_query(ch, sql)
                else:
                    err = str(first_err)
            except Exception as second_err:  # noqa: BLE001
                err = str(second_err)
        rows = _cap_rows(sql, rows)
        ev = {"type": "query", "n": i, "title": title, "sql": sql,
              "rows": rows, "cols": cols, "ms": ms, "error": err}
        results.append(ev)
        yield ev

    yield {"type": "status", "stage": "Writing the answer..."}
    try:
        text = synthesize_answer(question, results, model)
    except anthropic.APIError:
        text = ""
    yield {"type": "answer", "text": text}


def replay_scripts(scripts):
    """Re-run saved scripts live (no model, no tokens)."""
    ch = get_client()
    for i, spec in enumerate(scripts or [], 1):
        sql = (spec.get("sql") or "").strip()
        rows, cols, ms, err = [], [], 0.0, None
        try:
            rows, cols, ms = run_query(ch, sql)
            rows = _cap_rows(sql, rows)
        except Exception as e:  # noqa: BLE001
            err = str(e)
        yield {"type": "query", "n": i, "title": spec.get("title") or "Result",
               "sql": sql, "rows": rows, "cols": cols, "ms": ms, "error": err}


# --------------------------------------------------------------------------- #
# Terminal UI (Rich)
# --------------------------------------------------------------------------- #
def _preview_table(cols, rows, max_rows=15, max_cols=8):
    tbl = Table(box=box.SIMPLE, show_edge=False, header_style="bold cyan", pad_edge=False)
    for c in cols[:max_cols]:
        tbl.add_column(str(c), overflow="fold", max_width=22)
    for r in rows[:max_rows]:
        tbl.add_row(*[str(x)[:22] for x in r[:max_cols]])
    return tbl


def investigate(goal, schema, model=None, max_queries=None):
    console.print()
    console.print(Panel(Text(goal, style="bold white"), title="Question", title_align="left",
                        border_style="cyan", box=box.ROUNDED))
    with console.status("[cyan]Working...", spinner="dots"):
        events = list(answer(goal, schema, model))
    answer_text = ""
    for ev in events:
        if ev["type"] == "error":
            console.print(Panel(ev["message"], title="Error", border_style="red", box=box.ROUNDED))
        elif ev["type"] == "query":
            console.print(Panel(Syntax(ev["sql"], "sql", theme="ansi_dark", word_wrap=True,
                                       background_color="default"),
                                title=ev["title"], title_align="left", border_style="green", box=box.ROUNDED))
            if ev["error"]:
                console.print(Text(f"  query failed: {ev['error']}", style="red"))
            elif ev["rows"]:
                console.print(_preview_table(ev["cols"], ev["rows"]))
            else:
                console.print(Text("  (no rows)", style="dim"))
        elif ev["type"] == "answer":
            answer_text = ev["text"]
    if answer_text:
        console.print(Panel(Markdown(answer_text), title="Answer", title_align="left",
                            border_style="cyan", box=box.ROUNDED))
    return {"answer": answer_text}
