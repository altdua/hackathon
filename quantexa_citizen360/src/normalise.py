"""Turn dirty source_records into comparable keys.

Does not decide who is the same person. That is match.py.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IN_PATH = ROOT / "data" / "processed" / "source_records.csv"
OUT_PATH = ROOT / "data" / "processed" / "source_records_normalised.csv"

PC_RE = re.compile(r"^([A-Z]{1,2}\d[A-Z\d]?)(\d[A-Z]{2})$")
PHONE_RE = re.compile(r"\d+")

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

NICKNAMES = {
    "MAGGIE": {"MARGARET", "MAGGIE", "MAGS", "M"},
    "MARGARET": {"MARGARET", "MAGGIE", "MAGS", "M"},
    "MAGS": {"MARGARET", "MAGGIE", "MAGS", "M"},
    "CALLUM": {"CALLUM", "CAL", "C"},
    "CAL": {"CALLUM", "CAL", "C"},
    "IRENE": {"IRENE", "IRENA", "RENIE", "I"},
    "IRENA": {"IRENE", "IRENA", "RENIE", "I"},
    "RENIE": {"IRENE", "IRENA", "RENIE", "I"},
    "JOHN": {"JOHN", "JON", "J"},
    "DANIEL": {"DANIEL", "DAN", "D"},
}


def norm_postcode(value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    compact = re.sub(r"\s+", "", str(value).upper())
    m = PC_RE.match(compact)
    if not m:
        return compact
    return f"{m.group(1)} {m.group(2)}"


def postcode_sector(pc: str | None) -> str | None:
    if not pc:
        return None
    parts = pc.split()
    if len(parts) != 2:
        return None
    return f"{parts[0]} {parts[1][0]}"


def norm_phone(value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    digits = "".join(PHONE_RE.findall(str(value)))
    if digits.startswith("44") and len(digits) == 12:
        digits = "0" + digits[2:]
    return digits or None


def norm_dob(value: str | None) -> str | None:
    """Return ISO date YYYY-MM-DD, or YYYY-MM if only month+year, or YYYY."""
    if not value or not str(value).strip():
        return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    m = re.match(r"^([A-Za-z]+)\s+(\d{4})$", s)
    if m and m.group(1).lower() in MONTHS:
        return f"{m.group(2)}-{MONTHS[m.group(1).lower()]:02d}"
    m = re.match(r"^(\d{4})$", s)
    if m:
        return m.group(1)
    return None


def norm_name_part(value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    s = str(value).upper()
    s = s.replace("/", " ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # drop sex words leaked from Mosaic "Brennan / male"
    tokens = [t for t in s.split() if t not in {"MALE", "FEMALE", "MR", "MRS", "MS", "MISS"}]
    return " ".join(tokens) or None


def given_keys(given: str | None) -> str:
    if not given:
        return ""
    tokens = given.split()
    keys = set()
    for t in tokens:
        keys.add(t)
        keys.add(t[0])
        keys |= NICKNAMES.get(t, set())
    return "|".join(sorted(keys))


def aliases_from_payload(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    names = []
    for n in payload.get("name") or []:
        names.extend(n.get("given") or [])
        if n.get("family"):
            names.append(n["family"])
    return names


def run() -> pd.DataFrame:
    df = pd.read_csv(IN_PATH, dtype=str)
    df = df.fillna("")

    df["postcode_norm"] = df["postcode_raw"].map(lambda x: norm_postcode(x) or "")
    df["postcode_sector"] = df["postcode_norm"].map(lambda x: postcode_sector(x) or "")
    df["phone_norm"] = df["phone_raw"].map(lambda x: norm_phone(x) or "")
    df["dob_norm"] = df["dob_raw"].map(lambda x: norm_dob(x) or "")
    df["family_norm"] = df["family"].map(lambda x: norm_name_part(x) or "")
    df["given_norm"] = df["given"].map(lambda x: norm_name_part(x) or "")
    df["display_norm"] = df["name_display"].map(lambda x: norm_name_part(x) or "")

    # If family is empty, try first token of display (HALE M, Brennan / male, SMITH J)
    for i, row in df.iterrows():
        if not row["family_norm"] and row["display_norm"]:
            toks = row["display_norm"].split()
            # "HALE M" / "SMITH JOHN" / "BRENNAN C" — last token is often the given initial
            if len(toks) >= 2 and len(toks[-1]) <= 7:
                df.at[i, "family_norm"] = toks[0]
                if not row["given_norm"]:
                    df.at[i, "given_norm"] = " ".join(toks[1:])
            elif toks:
                df.at[i, "family_norm"] = toks[0]

    df["given_keys"] = df["given_norm"].map(given_keys)
    for i, row in df.iterrows():
        aliases = [norm_name_part(a) or "" for a in aliases_from_payload(row.get("payload_json"))]
        extra = [a for a in aliases if a]
        if extra:
            merged = " ".join([row["given_norm"], *extra]).strip()
            df.at[i, "given_keys"] = given_keys(merged)
    df["is_person_record"] = df["record_type"].isin(
        ["tenancy", "patient", "case", "visit", "COUNCIL_TAX", "DISTRICT_HEAT_RECHARGE"]
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    return df


if __name__ == "__main__":
    df = run()
    show = df[df["is_person_record"]][
        [
            "source",
            "source_record_id",
            "family_norm",
            "given_norm",
            "dob_norm",
            "postcode_norm",
            "phone_norm",
            "nhs_number",
            "uprn",
        ]
    ]
    print(show.to_string(index=False))
    print(f"\n{len(df)} rows -> {OUT_PATH}")
