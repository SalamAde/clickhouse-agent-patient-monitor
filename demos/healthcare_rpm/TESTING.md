# Testing the demo + questions to ask the agent

The agent takes any goal with `--goal`. Try these to see it reason differently
each time (the dataset seed is fixed, so the at-risk patients stay consistent
across runs - good for recording).

```bash
python demos/healthcare_rpm/run.py --goal "YOUR QUESTION HERE"
```

## Questions to ask the agent

### Clinical investigation (core)
1. "Which COPD patients are showing early signs of respiratory distress? Rank by urgency."
2. "Find diabetic patients with dangerous glucose trends this week and explain the pattern."
3. "Which patients had a sudden drop in activity in the last 3 days, and is it linked to other declining vitals?"
4. "Find patients deteriorating across at least 3 vital signs at once."
5. "Which patients look stable on average but are actually trending badly - the ones a simple threshold alert would miss?"
6. "Are there patients showing signs of a condition they are not diagnosed with?" (tests the 'undiagnosed' discovery)
7. "Which 5 patients should a nurse call first thing tomorrow, and what should she say to each?"
8. "Which patients are actually improving this week?" (can it flip direction?)

### Population / ops view (shows range)
9. "Give me a population summary: how many patients are stable vs watch vs critical right now?"
10. "Compare deterioration across regions. Is any region's cohort doing worse?"
11. "Which devices might be malfunctioning - patients with impossible or erratic readings?"
12. "Where are the gaps in our data coverage we should worry about?"

### Open-ended (shows real agentic reasoning)
13. "Tell me what I should be worried about." (deliberately vague - it decides)
14. "If you could only alert the care team about 3 patients, who and why?"

## Things to test on the system itself

- **Scale it up.** Regenerate bigger and watch query times stay low:
  `python demos/healthcare_rpm/generate_data.py --patients 40000 --timepoints 300` (~60M rows).
- **Swap the model.** Set `AGENT_MODEL=claude-opus-4-8` in `.env` and compare
  depth of reasoning vs Sonnet (Sonnet is faster/cheaper; Opus digs deeper).
- **Add a new metric** (e.g. temperature) to `schema.sql`, `generate_data.py`,
  and the schema text in `run.py` - the agent will use it with no other changes.
- **Make it harder to find.** Lower the at-risk share with
  `--deteriorating-pct 0.01` and see if it still surfaces the cohort.
- **Watch it self-correct.** If a query errors, the error is fed back and the
  agent rewrites the query - good to capture on video.

## What to point out while recording
- The variety of SQL it writes on its own (baseline vs recent, composite risk
  score, trajectory checks, multi-signal correlation).
- The millisecond timings next to every query.
- It finding the hidden deteriorating cohort that nobody told it to look for.
- The final tiered, evidence-backed report - written, not templated.
