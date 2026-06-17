# Agentic ClickHouse Demos

You ask a question in plain English. Claude writes the SQL, ClickHouse runs it,
and you get the answer back along with the exact query that produced it. Every
question is saved, so asking it again replays the SQL live at no model cost.

## Architecture

![Patient Risk Monitor architecture](assets/architecture.png)

A question travels from the Streamlit app to a two-phase Claude engine that first
plans the SQL, then summarises the rows. ClickHouse answers in about 30 ms. The
query is stored, so the next run replays it live for **0 AI tokens**.

---

## Demos

| # | Demo | What you can ask about |
|---|------|------------------------|
| 01 | [`healthcare_rpm`](demos/healthcare_rpm/) | Which patients are deteriorating in remote-monitoring data (~10M synthetic vitals) |

_More demos are on the way, such as marketing analytics. Each one is just a folder under `demos/`._

---

## Quick start (about 5 minutes)

**Prereqs:** Python 3.10+, an `ANTHROPIC_API_KEY`, and a **ClickHouse Cloud**
service (the free trial works, with nothing to install). To run the database on
your own machine instead, see [Local ClickHouse via Docker](#alternative-local-clickhouse-via-docker) below.

```bash
# 1. python deps
pip install -r requirements.txt

# 2. config: copy the template, then add your Anthropic key and ClickHouse Cloud
#    connection details (host and password from your Cloud service "Connect" panel)
cp .env.example .env

# 3. generate synthetic data (~10M rows; use --quick for a fast ~2M)
python demos/healthcare_rpm/generate_data.py

# 4. launch the web app and ask questions in plain English
streamlit run demos/healthcare_rpm/app.py
#    or use the terminal:  python demos/healthcare_rpm/run.py
```

Try a question like *"Which 10 patients have the lowest average SpO2 in the last
3 days?"*. Claude writes the SQL, ClickHouse Cloud answers in milliseconds, and
the query is saved for instant reuse later.

> All data is **100% synthetic**. No real people, no PHI.

### Alternative: local ClickHouse via Docker

To run ClickHouse on your own machine, uncomment the Option B (local) block in
your `.env`, then start the container:

```bash
docker compose up -d
```

Steps 1, 3, and 4 above stay the same.

---

## How it's built

```
src/core/
  db.py            # ClickHouse connection and timed query helper
  agent.py         # the reusable agentic loop (Claude tool-use plus a run_sql tool)
  saved_queries.py # persistent SQL store that replays live at no model cost
demos/
  healthcare_rpm/
    schema.sql        # ClickHouse tables
    generate_data.py  # synthetic data generator
    app.py            # Streamlit UI: ask questions, get SQL and results
    run.py            # same investigation from the terminal
```

**To add a new demo:** create `demos/<your_demo>/` with its own `schema.sql`,
`generate_data.py`, and a `run.py` that calls `investigate(goal, schema)`. The
agent core stays the same.

The agent loop is easy to follow: one tool (`run_sql`), a plain message loop, and
a prompt-cached system prompt and schema that keep a multi-step investigation
cheap. Set `AGENT_MODEL` in `.env` to trade speed for reasoning, using
`claude-sonnet-4-6` for speed or `claude-opus-4-8` for harder questions.
