CREATE TABLE IF NOT EXISTS patients
(
    patient_id  UInt32,
    age         UInt8,
    sex         Enum8('F' = 1, 'M' = 2),
    condition   LowCardinality(String),
    region      LowCardinality(String),
    enrolled_at Date
)
ENGINE = MergeTree
ORDER BY patient_id;

CREATE TABLE IF NOT EXISTS vitals
(
    event_time DateTime,
    patient_id UInt32,
    metric     LowCardinality(String),
    value      Float32,
    device_id  UInt32
)
ENGINE = MergeTree
ORDER BY (patient_id, metric, event_time);
