# LinkedIn launch post - Demo #1

everyone's building AI agents.

almost no one is talking about what actually makes them work.

i spent this weekend building something to prove a point i can't stop thinking about: an AI agent is only as smart as the database underneath it.

here's what i built (100% synthetic data, zero real patients):

10 million remote patient-monitoring readings - heart rate, oxygen, glucose, blood pressure - sitting in ClickHouse.

then i gave an AI agent one instruction. not a query. a goal:

"find the patients most at risk of deterioration this week, and tell the care team who to call first."

no SQL written by me. no dashboard. just a goal.

what happened next is the whole point:

the agent investigated on its own. it profiled the data, built each patient's personal baseline, scored five vital signs, checked whether each decline was real or just noise, then cross-referenced who was failing on multiple fronts at once.

→ 16 queries
→ across 10,000,000 records
→ ~3 seconds

and it found them. a cluster of heart-failure patients quietly collapsing - oxygen sliding, heart rate climbing, movement halving - days before it would've shown up on a dashboard. it even flagged one patient whose data hinted at undiagnosed diabetes.

here's the part most people miss:

this only works because the database is fast.

an agent that investigates runs dozens of queries to answer one question. on a slow database that's minutes per step and a bill that makes the whole thing pointless. on ClickHouse - milliseconds per query - the agent can think in real time.

the agent is the brain. ClickHouse is what lets it think fast.

this is what i'm building now: the data infrastructure layer that AI and analytics products run on.

healthcare today. it's demo #1 of many.

code's on GitHub (link in comments). all data synthetic - no PHI.

what would you point an agent like this at?

---

## Shorter alternative hook (if you want a punchier open)
> i gave an AI agent 10 million patient records and one sentence: "who's about to crash, and who do we call first?"
>
> it ran 16 queries in 3 seconds and found them. here's why the database - not the AI - is the real story 👇
