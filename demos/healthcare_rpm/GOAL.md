# Demo 01 - Healthcare RPM: agentic risk investigation

**The problem:** A remote-patient-monitoring program streams millions of vitals
readings. Answers are (a) too slow - legacy databases choke on the volume - and
(b) gated behind a data engineer who has to write the SQL. A nurse who wants
"who's deteriorating this week?" waits hours or days.

**What this demo proves:** Give an AI agent a *goal*, not a query. It investigates
autonomously - running many ClickHouse queries, reading results, drilling into
anomalies, correlating across metrics - and returns a ranked, evidence-backed
risk report in seconds. It works only because every query returns in
milliseconds: **ClickHouse is the engine that makes the agent viable.**

**The goal we give it:**
> Find the patients most at risk of clinical deterioration in the last 7 days.
> Explain why each is at risk using the data, and tell the care team who to
> contact first.

**What to watch:** the agent runs ~15-20 queries over ~10M rows and finishes in
seconds - and surfaces the hidden deteriorating cohort that nobody told it to
look for.

_Data is 100% synthetic. No real patients, no PHI._
