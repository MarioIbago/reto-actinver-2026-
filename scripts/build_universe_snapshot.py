#!/usr/bin/env python3
"""Build the M1 universe JSON from immutable repository source snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUIDE_PATH = ROOT / "research/source_material/reto-actinver-2026-guia.md"
SYMBOLS_PATH = ROOT / "research/source_material/actinver_universe_symbols_raw.md"
DEFAULT_OUTPUT = ROOT / "data/metadata/actinver_universe_2026_v1.json"
OFFICIAL_GUIDE = (
    "https://www.retoactinver.com/documents/d/reto-actinver/"
    "guia-participante_reto-actinver-2026"
)

CATEGORIES = {
    "Acciones nacionales": ("national_equity", "acciones_nacionales"),
    "Acciones del SIC": ("sic_equity", "acciones_sic"),
    "Fondos": ("fund", "fondos"),
    "ETFs": ("etf", "etfs"),
    "FIBRAs": ("fibra", "fibras"),
}
EXPECTED_COUNTS = {
    "national_equity": 40,
    "sic_equity": 100,
    "fund": 23,
    "etf": 40,
    "fibra": 4,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")


def parse_guide_tables(text: str) -> dict[str, list[tuple[str, str]]]:
    parsed = {code: [] for code, _ in CATEGORIES.values()}
    category = None
    for line in text.splitlines():
        heading = re.fullmatch(r"###\s+(.+?)\s*", line)
        if heading:
            category = CATEGORIES.get(heading.group(1), (None, None))[0]
            continue
        if category is None or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 2 or cells[0] in {"Emisora", "---"}:
            continue
        if set(cells[0]) <= {"-", ":", " "}:
            continue
        parsed[category].append((cells[0], cells[1]))
    return parsed


def parse_compact_symbols(text: str) -> dict[str, set[str]]:
    raw_names = {raw: code for code, raw in CATEGORIES.values()}
    parsed = {code: set() for code, _ in CATEGORIES.values()}
    current = None
    for line in text.splitlines():
        heading = re.fullmatch(r"##\s+([^\s]+)\s*", line)
        if heading:
            current = raw_names.get(heading.group(1))
            continue
        if current is None or not line.strip():
            continue
        for symbol in line.strip().split(", "):
            if symbol:
                parsed[current].add(symbol)
    return parsed


def build(verified_at_utc: str) -> dict:
    guide_bytes = GUIDE_PATH.read_bytes()
    compact_bytes = SYMBOLS_PATH.read_bytes()
    guide = parse_guide_tables(guide_bytes.decode("utf-8-sig"))
    compact = parse_compact_symbols(compact_bytes.decode("utf-8-sig"))
    instruments = []
    counts = {}

    for category_name, (category_code, _raw_category) in CATEGORIES.items():
        records = guide[category_code]
        counts[category_code] = len(records)
        guide_symbols = [symbol for symbol, _name in records]
        if len(guide_symbols) != len(set(guide_symbols)):
            raise ValueError(f"Duplicate symbol in source guide category {category_name}")
        if set(guide_symbols) != compact[category_code]:
            added = sorted(set(guide_symbols) - compact[category_code])
            missing = sorted(compact[category_code] - set(guide_symbols))
            raise ValueError(
                f"Guide/raw-symbol mismatch for {category_code}: "
                f"only_in_guide={added}; only_in_compact_snapshot={missing}"
            )
        if counts[category_code] != EXPECTED_COUNTS[category_code]:
            raise ValueError(
                f"Unexpected {category_code} count: {counts[category_code]}"
            )

        for guide_symbol, issuer_or_name in records:
            symbol_slug = slug(guide_symbol)
            fibers_conflict = category_code == "fibra"
            instruments.append(
                {
                    "instrument_id": f"actinver:2026:{category_code}:{symbol_slug}",
                    "issuer_key": f"actinver:2026:issuer:{category_code}:{symbol_slug}",
                    "category": category_code,
                    "instrument_type": category_code,
                    "guide_symbol": guide_symbol,
                    "issuer_or_name": issuer_or_name,
                    "platform_symbol": None,
                    "series": None,
                    "currency": None,
                    "sector": None,
                    "liquidity_attributes": None,
                    "qualifying_share_under_rules_page": category_code
                    in {"national_equity", "sic_equity"},
                    "eligibility": {
                        "listed_in_official_2026_guide_annex": True,
                        "rulebook_category_conflict": fibers_conflict,
                        "platform_search_symbol_verified": False,
                        "valid_from": "2026-10-05",
                        "valid_to": "2026-11-13",
                        "valid_from_basis": "Competition start date; per-instrument annex validity dates are not stated.",
                    },
                    "source_id": "participant_guide_2026",
                }
            )

    counts["total"] = len(instruments)
    if counts["total"] != sum(EXPECTED_COUNTS.values()):
        raise ValueError(f"Unexpected total instrument count: {counts['total']}")

    return {
        "schema_version": 1,
        "snapshot_id": "actinver-2026-guide-annex-v1",
        "status": "guide_annex_normalized_platform_symbols_unverified",
        "observed_at_utc": verified_at_utc,
        "effective_from": "2026-10-05",
        "effective_to": "2026-11-13",
        "effective_from_basis": "Competition period in official 2026 rules; the guide gives no per-instrument dates, so dates follow the contest window.",
        "source": {
            "source_id": "participant_guide_2026",
            "publisher": "Actinver",
            "title": "Guía editorial del participante Reto Actinver 2026",
            "url": OFFICIAL_GUIDE,
            "annex_pages": "29-41",
            "repository_guide_snapshot": "research/source_material/reto-actinver-2026-guia.md",
            "repository_guide_snapshot_sha256": hashlib.sha256(guide_bytes).hexdigest(),
            "repository_symbol_list_snapshot": "research/source_material/actinver_universe_symbols_raw.md",
            "repository_symbol_list_sha256": hashlib.sha256(compact_bytes).hexdigest(),
            "source_match": "guide_table_symbols_equal_compact_raw_symbol_list_by_category",
        },
        "expected_counts": EXPECTED_COUNTS | {"total": 207},
        "observed_counts": counts,
        "identifier_policy": {
            "instrument_id": "Stable repository identifier from category and guide symbol; not a vendor or exchange ID.",
            "issuer_key": "Stable source-local key; not a legal-entity identifier.",
            "guide_symbol": "Copied verbatim from the official guide table snapshot.",
            "platform_symbol": "Null until directly checked in the simulator search.",
            "series": "Null until directly checked in the simulator search.",
        },
        "instruments": instruments,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verified-at-utc", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    snapshot = build(args.verified_at_utc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"Wrote {args.output} with {snapshot['observed_counts']['total']} "
        "source-listed instruments."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
