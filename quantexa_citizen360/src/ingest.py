"""Load the five mock public-sector extracts into one source_records table.

Does not resolve entities. Does not clean names/postcodes beyond copying
fields out of each native schema. Next step: normalise + match.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

COLUMNS = [
    "source",
    "source_record_id",
    "record_type",
    "family",
    "given",
    "name_display",
    "dob_raw",
    "sex_raw",
    "address_raw",
    "postcode_raw",
    "phone_raw",
    "nhs_number",
    "uprn",
    "payload_json",
]


def _row(**kwargs) -> dict:
    out = {k: None for k in COLUMNS}
    out.update(kwargs)
    if out.get("payload_json") is not None and not isinstance(out["payload_json"], str):
        out["payload_json"] = json.dumps(out["payload_json"], default=str)
    return out


def ingest_housing(path: Path) -> list[dict]:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    rows = []
    for rec in df.to_dict(orient="records"):
        addr = ", ".join(
            p for p in [rec.get("ADDR1"), rec.get("ADDR2"), rec.get("ADDR3")] if p
        )
        rows.append(
            _row(
                source="mcc_housing",
                source_record_id=rec.get("TENANCY_REF"),
                record_type="tenancy",
                family=rec.get("SURNAME") or None,
                given=rec.get("FORENAME") or None,
                name_display=" ".join(
                    p for p in [rec.get("TITLE"), rec.get("FORENAME"), rec.get("SURNAME")] if p
                )
                or None,
                dob_raw=rec.get("DOB") or None,
                address_raw=addr or None,
                postcode_raw=rec.get("POSTCODE") or None,
                phone_raw=rec.get("CONTACT_TEL") or None,
                payload_json=rec,
            )
        )
    return rows


def ingest_gp(path: Path) -> list[dict]:
    bundle = json.loads(path.read_text())
    rows = []
    for entry in bundle.get("entry", []):
        res = entry.get("resource") or {}
        rtype = res.get("resourceType")
        if rtype == "Patient":
            nhs = None
            for ident in res.get("identifier") or []:
                if ident.get("system") == "https://fhir.nhs.uk/Id/nhs-number":
                    nhs = ident.get("value")
            name = (res.get("name") or [{}])[0]
            addr = (res.get("address") or [{}])[0]
            phone = None
            for tel in res.get("telecom") or []:
                if tel.get("system") == "phone":
                    phone = tel.get("value")
                    break
            given = " ".join(name.get("given") or []) or None
            family = name.get("family")
            rows.append(
                _row(
                    source="gp_emis",
                    source_record_id=res.get("id"),
                    record_type="patient",
                    family=family,
                    given=given,
                    name_display=" ".join(
                        p for p in [given, family] if p) or None,
                    dob_raw=res.get("birthDate"),
                    sex_raw=res.get("gender"),
                    address_raw=", ".join(
                        (addr.get("line") or []) + [addr.get("city") or ""]
                    ).strip(", ")
                    or None,
                    postcode_raw=addr.get("postalCode"),
                    phone_raw=phone,
                    nhs_number=nhs,
                    payload_json=res,
                )
            )
        elif rtype in {"Appointment", "Condition"}:
            subject = (res.get("subject") or {}).get("reference", "")
            rows.append(
                _row(
                    source="gp_emis",
                    source_record_id=res.get("id"),
                    record_type=rtype.lower(),
                    payload_json={
                        "subject": subject,
                        "status": res.get("status") or (res.get("clinicalStatus") or {}),
                        "description": res.get("description")
                        or (res.get("code") or {}).get("text"),
                        "start": res.get("start"),
                        "onsetDateTime": res.get("onsetDateTime"),
                    },
                )
            )
    return rows


def ingest_social_care(path: Path) -> list[dict]:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    rows = []
    for rec in df.to_dict(orient="records"):
        rows.append(
            _row(
                source="adult_social_care",
                source_record_id=rec.get("CaseID"),
                record_type="case",
                name_display=rec.get("DisplayName") or None,
                dob_raw=rec.get("DOB_Text") or None,
                sex_raw=rec.get("AgeSex") or None,
                address_raw=rec.get("AddressAsRecorded") or None,
                postcode_raw=rec.get("Postcode") or None,
                uprn=rec.get("UPRN") or None,
                payload_json=rec,
            )
        )
    return rows


def ingest_foodbank(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        rows.append(
            _row(
                source="foodbank",
                source_record_id=rec.get("visit_id"),
                record_type="visit",
                given=rec.get("first_name") or None,
                name_display=rec.get("first_name") or None,
                postcode_raw=rec.get("postcode") or None,
                payload_json=rec,
            )
        )
    return rows


def ingest_revenues(path: Path) -> list[dict]:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    rows = []
    for rec in df.to_dict(orient="records"):
        rows.append(
            _row(
                source="revenues_energy",
                source_record_id=rec.get("ACCOUNT_REF"),
                record_type=rec.get("ACCOUNT_TYPE") or "account",
                name_display=rec.get("ACCOUNT_NAME") or None,
                address_raw=rec.get("ADDR_FULL") or None,
                postcode_raw=rec.get("POSTCODE") or None,
                uprn=rec.get("UPRN") or None,
                payload_json=rec,
            )
        )
    return rows


def run() -> pd.DataFrame:
    parts = [
        ingest_housing(RAW / "mcc_housing_tenancies_extract.csv"),
        ingest_gp(RAW / "gp_emis_extract_mft.json"),
        ingest_social_care(RAW / "adult_social_care_mosaic_extract.csv"),
        ingest_foodbank(RAW / "foodbank_visits_ancoats.jsonl"),
        ingest_revenues(RAW / "revenues_and_energy_debt_flags.csv"),
    ]
    df = pd.DataFrame([r for chunk in parts for r in chunk], columns=COLUMNS)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "source_records.csv", index=False)
    try:
        df.to_parquet(OUT / "source_records.parquet", index=False)
    except ImportError:
        pass
    return df


if __name__ == "__main__":
    df = run()
    print(df.groupby(["source", "record_type"]).size().to_string())
    print(f"\n{len(df)} rows -> {OUT / 'source_records.csv'}")
