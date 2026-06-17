# Agentic ClickHouse Demos

Small, reproducible demos showing the same idea in different domains:

> **Agentic AI is only as good as the engine underneath it.**
> An agent that *investigates* runs dozens of queries to answer one goal.
> On a slow database that's unusable. On ClickHouse - milliseconds per query -
> the agent thinks fast enough to be genuinely useful.
> **ClickHouse is the engine behind AI agents.**

You give the agent a **goal**, not a question. It plans, runs many ClickHouse
queries, reads the results, drills into anomalies, and returns an
evidence-backed conclusion + recommended action - in seconds.

## Architecture

![Patient Risk Monitor architecture](assets/architecture.png)

A question flows from the Streamlit app to a two-phase Claude engine (plan the SQL,
then summarize the rows), runs against ClickHouse in ~30 ms, and is saved so the
next run replays the SQL live with **0 AI tokens**.

---

## Demos

| # | Demo | What the agent investigates |
|---|------|------------------------------|
| 01 | [`healthcare_rpm`](demos/healthcare_rpm/) | Finds patients deteriorating in remote-monitoring data (~10M synthetic vitals) |

_(More coming - marketing analytics, etc. Each new demo is just a folder under `demos/`.)_

---

## Quick start (≈5 minutes)

**Prereqs:** Python 3.10+, an `ANTHROPIC_API_KEY`, and a **ClickHouse Cloud**
service (free trial - no install). Prefer to run the database locally instead?
See [Local ClickHouse via Docker](#alternative-local-clickhouse-via-docker) below.

```bash
# 1. python deps
pip install -r requirements.txt

# 2. config: copy the template, then add your Anthropic key + ClickHouse Cloud
#    connection details (host/password from your Cloud service "Connect" panel)
cp .env.example .env

# 3. generate synthetic data (~10M rows; use --quick for a fast ~2M)
python demos/healthcare_rpm/generate_data.py

# 4. launch the web app and ask questions in plain English
streamlit run demos/healthcare_rpm/app.py
#    ...or use the terminal:  python demos/healthcare_rpm/run.py
```

Ask something like *"Which 10 patients have the lowest average SpO2 in the last
3 days?"* - Claude writes the SQL, ClickHouse Cloud answers in milliseconds, and
the query is saved so re-running it later costs **0 AI tokens**.

> All data is **100% synthetic**. No real people, no PHI.

### Alternative: local ClickHouse via Docker

Prefer not to use the cloud? Run ClickHouse locally instead - uncomment the
Option B (local) block in your `.env`, then:

```bash
docker compose up -d
```

Everything else (steps 1, 3, and 4 above) is identical.

---

## How it's built

```
src/core/
  db.py            # ClickHouse connection + timed query helper
  agent.py         # the reusable agentic loop (Claude tool-use + run_sql tool)
  saved_queries.py # persistent SQL store - replay live with 0 AI tokens
demos/
  healthcare_rpm/
    schema.sql        # ClickHouse tables
    generate_data.py  # synthetic data generator
    app.py            # Streamlit UI - ask questions, get SQL + results
    run.py            # same investigation from the terminal
```

**To add a new demo:** create `demos/<your_demo>/` with its own `schema.sql`,
`generate_data.py`, and a `run.py` that calls `investigate(goal, schema)`.
The agent core doesn't change.

The agent loop is deliberately transparent - one tool (`run_sql`), a plain
message loop, prompt-cached system/schema so the multi-step investigation stays
cheap. Swap `AGENT_MODEL` in `.env` (`claude-sonnet-4-6` for speed,
`claude-opus-4-8` for max reasoning).
