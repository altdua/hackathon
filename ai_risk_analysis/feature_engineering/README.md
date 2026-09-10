# Feature engineering

Part 3 prototype: combine calculated numerical indicators and evidence-backed
text observations into one structured feature record per citizen. Python 3.10+
and the standard library are sufficient. No dependencies need installing.

The pipeline expects already linked and standardised citizen data from part 2.
It does not perform entity resolution, train a risk model, score citizens, or
recommend interventions. The text extractor is replaceable via an object with
`name` and `extract(notes)`; multiple autonomous agents are not required.

## Run the synthetic example

From the project root:

```powershell
python -m feature_engineering --input feature_engineering/examples/citizens.json --output feature_engineering/output --as-of 2026-09-10 --extractor demo
python -m unittest feature_engineering.test_pipeline -v
```

Demo mode only recognises exact synthetic marker sentences in the example.
It is not an LLM or a general text analyser. Ordinary notes produce unknown
indicators in this mode. No network calls are made.

The output directory receives `features.json` (features and audit evidence) and
`features.csv` (flat numeric features with citizen ID and cutoff date). Repeating
the command replaces those two files. CSV blanks and JSON nulls mean unknown,
with explicit missing flags. Exclude citizen_id and as_of from model predictors;
handle missing values in your downstream training pipeline. Fit preprocessing
on training data only. Evidence remains in the JSON audit record.

## Use an LLM for ordinary case notes

Set OPENAI_API_KEY in your environment using your preferred secret-management
method. Then choose a model available to your account that supports structured
outputs:

```powershell
python -m feature_engineering --input path/to/citizens.json --output feature_engineering/output --as-of 2026-09-10 --extractor openai --model YOUR_MODEL_ID
```

This explicitly selected mode sends eligible note IDs, dates, and text to the
OpenAI API. Citizen IDs and numerical records are not sent. Text itself may
contain identifying information: use synthetic or appropriately prepared,
approved data. No automatic anonymisation is implemented. Local JSON output
also contains note text and evidence. Store it with the source data's access
controls. The request sets store=false; this is not a claim of zero retention.

The adapter uses the Responses API with a strict JSON schema, following the
[official Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs).
API failures, refusals, incomplete responses and invalid evidence stop the run;
they do not silently become negative indicators. There are no automatic retries.

## Input contract

Input is a nonempty JSON list; each object requires a unique citizen_id. See
examples/citizens.json for the complete shape. Source lists are:

| Source | Fields per record |
| --- | --- |
| housing | date, recorded_at, arrears_amount |
| appointments | appointment_id, date, recorded_at, status: attended/missed/cancelled |
| notes | note_id, date, recorded_at, text |

Dates use YYYY-MM-DD. `date` is the event/snapshot date and `recorded_at` is
when the record became available. Both must be on or before the cutoff.
recorded_at must not precede date. Use the time that the actual record version
became available to avoid backfilled information leaking into historical runs.
Missing/null lists mean unavailable; [] means checked and empty. Appointment
and note IDs must be unique within each eligible citizen source list. Resolve
duplicate housing dates upstream. All housing amounts must use the same currency.

## Feature definitions

| Feature | Meaning |
| --- | --- |
| rent_arrears_amount | Latest eligible housing snapshot amount |
| arrears_snapshot_age_days | Age of that snapshot at cutoff |
| arrears_change_observed_90d | Last minus first amount within 90 days; null with fewer than two snapshots |
| missed_appointments_90d | Number of missed appointments within 90 days |
| missed_appointment_rate_90d | Missed / (attended + missed); cancelled excluded; null with no denominator |
| text_social_isolation | Documented isolation observation |
| text_housing_concern | Documented housing concern observation |
| text_financial_hardship | Documented financial hardship observation |
| text_safeguarding_concern | Documented safeguarding concern observation |
| notes_count_90d | Eligible notes, or null when source unavailable |

90-day windows exclude the date exactly 90 days before cutoff and include the
cutoff day. Housing amount may come from an older snapshot; its age is explicit.
Observed arrears change is not an extrapolated 90-day trend. Source coverage is
assumed for supplied lists; incomplete feeds need explicit coverage metadata
before deployment.

Text values are 1=explicitly present, 0=explicitly absent, null=unknown or
conflicting. Each has a conflict flag, and all base features have missing flags.
The JSON audit retains status, exact quotations, source note IDs, dates,
numerical source records, extractor identity and schema version.

Quoted evidence is checked against source text, but that does not prove the
model interpreted it correctly. Before using real outputs, evaluate extraction
on labelled notes including negation, historical mentions, third-party mentions,
contradictions and instructions embedded in notes. Live LLM accuracy and risk
prediction quality have not been evaluated by the included offline tests.
