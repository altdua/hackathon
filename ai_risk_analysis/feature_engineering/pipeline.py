"""Point-in-time feature assembly from already linked citizen records."""

from datetime import date, timedelta
import math

from .text import INDICATORS, unknown_observations, validate_observations


def parse_date(value):
    if not isinstance(value, str):
        raise ValueError("Dates must be ISO YYYY-MM-DD strings")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Dates must be ISO YYYY-MM-DD strings")
    return parsed


def eligible(records, as_of, window_days=None):
    if not isinstance(records, list):
        raise ValueError("Record collections must be lists")
    result = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Records must be objects")
        event_date = parse_date(record["date"])
        known_date = parse_date(record["recorded_at"])
        if known_date < event_date:
            raise ValueError("recorded_at cannot precede the event date")
        if event_date > as_of or known_date > as_of:
            continue
        if window_days is None or event_date > as_of - timedelta(days=window_days):
            result.append(record)
    return result


def amount(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("Arrears amounts must be finite nonnegative numbers")
    return value


def build_features(citizen, as_of, extractor):
    """Return numeric model inputs plus a separate audit record.

    Missing/null source lists mean unavailable. An empty list means the source
    was checked and contains no records. Windows are (as_of - 90 days, as_of].
    """
    cutoff = parse_date(as_of)
    if not isinstance(citizen.get("citizen_id"), str) or not citizen["citizen_id"].strip():
        raise ValueError("A nonempty citizen_id is required")
    features = {}
    audit = {"schema_version": "1.0", "extractor": extractor.name, "numeric_sources": {}}
    housing = citizen.get("housing")
    snapshots = eligible(housing, cutoff) if housing is not None else []
    for item in snapshots:
        amount(item["arrears_amount"])
    snapshots.sort(key=lambda x: (x["date"], x["recorded_at"]))
    if len({s["date"] for s in snapshots}) != len(snapshots):
        raise ValueError("Housing must contain one resolved snapshot per date")
    latest = snapshots[-1] if snapshots else None
    recent = [s for s in snapshots if parse_date(s["date"]) > cutoff - timedelta(days=90)]
    features["rent_arrears_amount"] = latest["arrears_amount"] if latest else None
    features["arrears_snapshot_age_days"] = (cutoff - parse_date(latest["date"])).days if latest else None
    features["arrears_change_observed_90d"] = (recent[-1]["arrears_amount"] - recent[0]["arrears_amount"]) if len(recent) >= 2 else None
    audit["numeric_sources"]["housing"] = snapshots
    appointments = citizen.get("appointments")
    visits = eligible(appointments, cutoff, 90) if appointments is not None else []
    ids = set()
    for visit in visits:
        if not isinstance(visit.get("appointment_id"), str) or not visit["appointment_id"].strip():
            raise ValueError("Appointments need nonempty appointment_id values")
        if visit["appointment_id"] in ids:
            raise ValueError("Duplicate appointment_id; resolve duplicates upstream")
        ids.add(visit["appointment_id"])
        if visit.get("status") not in ("attended", "missed", "cancelled"):
            raise ValueError("Invalid appointment status")
    missed = sum(v["status"] == "missed" for v in visits)
    completed = sum(v["status"] != "cancelled" for v in visits)
    features["missed_appointments_90d"] = missed if appointments is not None else None
    features["missed_appointment_rate_90d"] = missed / completed if completed else None
    audit["numeric_sources"]["appointments"] = visits
    notes_raw = citizen.get("notes")
    notes = eligible(notes_raw, cutoff, 90) if notes_raw is not None else []
    note_ids = set()
    for note in notes:
        if not isinstance(note.get("note_id"), str) or not note["note_id"].strip() or note["note_id"] in note_ids:
            raise ValueError("Notes need unique nonempty note_id values")
        note_ids.add(note["note_id"])
        if not isinstance(note.get("text"), str) or not note["text"].strip():
            raise ValueError("Note text must be nonempty")
    # Whitelist the fields sent to the text provider; citizen_id stays local.
    text_input = [{k: n[k] for k in ("note_id", "date", "recorded_at", "text")} for n in notes]
    observations = validate_observations(extractor.extract(text_input), text_input) if notes else unknown_observations()
    for name in INDICATORS:
        status = observations[name]["status"]
        features[f"text_{name}"] = {"present": 1, "absent": 0}.get(status)
        features[f"text_{name}_conflicting"] = int(status == "conflicting")
    features["notes_count_90d"] = len(notes) if notes_raw is not None else None
    audit["text_observations"] = observations
    audit["notes"] = text_input
    audit["unavailable_sources"] = [k for k in ("housing", "appointments", "notes") if citizen.get(k) is None]
    # Missing flags allow downstream imputation without confusing unknown with zero.
    features.update({f"{k}_missing": int(v is None) for k, v in list(features.items())})
    return {"citizen_id": citizen["citizen_id"], "as_of": as_of, "features": features, "audit": audit}
