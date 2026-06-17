"""Shared config for the healthcare RPM demo (used by both run.py and app.py)."""

SCHEMA = """
Table `patients` (one row per enrolled patient):
  patient_id UInt32, age UInt8, sex Enum('F','M'),
  condition LowCardinality(String)  -- one of: Healthy, Hypertension, Diabetes, COPD, CHF
  region LowCardinality(String), enrolled_at Date

Table `vitals` (remote-monitoring readings, ~10M rows, last 30 days):
  event_time DateTime, patient_id UInt32,
  metric LowCardinality(String)  -- one of: heart_rate, spo2, systolic_bp, glucose, steps
  value Float32, device_id UInt32

Clinical interpretation (higher = worse unless noted):
  - heart_rate: elevated/rising is concerning
  - spo2: blood oxygen %, LOWER is worse (below ~92 is a red flag)
  - systolic_bp: higher is worse (above ~140 concerning)
  - glucose: higher is worse (spikes above ~180 concerning, esp. Diabetes)
  - steps: activity level, a sharp DROP can indicate decline
Join vitals.patient_id = patients.patient_id to segment by condition/age/region.
Compare each patient's recent readings (last ~3 days) to their earlier baseline
to spot deterioration -- a trend matters more than a single value.
""".strip()

DEFAULT_GOAL = (
    "Find the patients most at risk of clinical deterioration in the last 7 days. "
    "Explain WHY each is at risk using the data, and tell the care team which "
    "patients to contact first."
)

EXAMPLES = [
    "Find the patients most at risk of clinical deterioration in the last 7 days.",
    "Which COPD patients are showing early signs of respiratory distress? Rank by urgency.",
    "Which 10 patients have the lowest average SpO2 in the last 3 days?",
    "What is the average heart rate by condition?",
    "Which patients had a sharp glucose spike this week?",
    "Tell me what I should be worried about.",
]
