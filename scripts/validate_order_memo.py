"""Validate and bundle a manual-only Actinver watchlist memo for GitHub Actions."""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import math
from pathlib import Path
import re
import shutil
import sys
from typing import Any
from urllib.parse import urlparse


WATCHLIST = frozenset({
    "BA", "AVGO", "NVDA", "AMAT", "WFC", "AMXB", "GAPB", "GMEXICOB",
    "PE&OLES", "ASURB", "OMAB", "VOLARA", "GFNORTEO", "WALMEX",
    "CEMEXCPO", "ALPEKA",
})
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STATUSES = frozenset({"WATCH", "NO_TRADE", "WAIT_FOR_PULLBACK", "WAIT_FOR_CONFIRMATION"})


class MemoValidationError(ValueError):
    """Raised when a memo is incomplete, stale by contract, or unsafe to publish."""


def _is_https_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return timestamp.tzinfo is not None


def validate_memo(memo: Any, expected_date: str | None = None) -> dict[str, Any]:
    """Fail closed unless the document covers the fixed watchlist and has no orders."""
    if not isinstance(memo, dict):
        raise MemoValidationError("memo root must be a JSON object")
    if memo.get("schema_version") != 1:
        raise MemoValidationError("schema_version must be 1")
    for field in ("memo_id", "for_session_date", "prepared_at_utc", "decision_status",
                  "execution_policy", "watchlist", "orders", "sources"):
        if field not in memo:
            raise MemoValidationError(f"missing required field: {field}")

    session_date = memo["for_session_date"]
    if not isinstance(session_date, str) or not DATE_PATTERN.fullmatch(session_date):
        raise MemoValidationError("for_session_date must use YYYY-MM-DD")
    try:
        date.fromisoformat(session_date)
    except ValueError as exc:
        raise MemoValidationError("for_session_date is not a calendar date") from exc
    if expected_date is not None and session_date != expected_date:
        raise MemoValidationError(
            f"memo session date {session_date} does not match requested date {expected_date}"
        )
    if not _valid_timestamp(memo["prepared_at_utc"]):
        raise MemoValidationError("prepared_at_utc must be an ISO timestamp with timezone")
    if memo["decision_status"] != "NO_TRADE":
        raise MemoValidationError("published memo must remain NO_TRADE")
    if memo["memo_id"] != f"ACTINVER-WATCHLIST-{session_date}":
        raise MemoValidationError("memo_id must match the session date")
    if memo["execution_policy"] != "MANUAL_ONLY":
        raise MemoValidationError("execution_policy must be MANUAL_ONLY")
    if memo.get("actinver_order_entry_enabled") is not False:
        raise MemoValidationError("actinver_order_entry_enabled must be false")
    if memo.get("portfolio_state_verified") is not False:
        raise MemoValidationError("portfolio_state_verified must be false for this report")
    if memo["orders"] != []:
        raise MemoValidationError("orders must be an empty list; this workflow never publishes orders")

    instruments = memo["watchlist"]
    if not isinstance(instruments, list) or len(instruments) != len(WATCHLIST):
        raise MemoValidationError(f"watchlist must contain exactly {len(WATCHLIST)} instruments")
    seen: set[str] = set()
    for instrument in instruments:
        if not isinstance(instrument, dict):
            raise MemoValidationError("each watchlist entry must be a JSON object")
        ticker = instrument.get("ticker")
        if ticker not in WATCHLIST:
            raise MemoValidationError(f"unexpected watchlist ticker: {ticker!r}")
        if ticker in seen:
            raise MemoValidationError(f"duplicate watchlist ticker: {ticker}")
        seen.add(ticker)
        if instrument.get("status") not in STATUSES:
            raise MemoValidationError(f"{ticker}: status must be one of {sorted(STATUSES)}")
        if not isinstance(instrument.get("name"), str) or not instrument["name"].strip():
            raise MemoValidationError(f"{ticker}: name is required")
        if instrument.get("actinver_identity_verified") is not False:
            raise MemoValidationError(f"{ticker}: Actinver identity must remain unverified")
        if not isinstance(instrument.get("watch_condition"), str) or not instrument["watch_condition"].strip():
            raise MemoValidationError(f"{ticker}: watch_condition is required")
        urls = instrument.get("source_urls")
        if not isinstance(urls, list) or not urls or any(not _is_https_url(url) for url in urls):
            raise MemoValidationError(f"{ticker}: source_urls must contain HTTPS URLs")

        quote = instrument.get("quote")
        if not isinstance(quote, dict):
            raise MemoValidationError(f"{ticker}: quote metadata is required")
        if quote.get("actionable") is not False:
            raise MemoValidationError(f"{ticker}: quote must be marked non-actionable")
        if quote.get("price") is not None:
            price = quote["price"]
            if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
                raise MemoValidationError(f"{ticker}: quote price must be a positive finite number or null")
            if not _valid_timestamp(quote.get("observed_at_local")):
                raise MemoValidationError(f"{ticker}: quote timestamp must include a timezone")
            if not _is_https_url(quote.get("source_url")):
                raise MemoValidationError(f"{ticker}: quote source_url must be HTTPS")

    if seen != WATCHLIST:
        missing = sorted(WATCHLIST - seen)
        raise MemoValidationError(f"watchlist is missing tickers: {', '.join(missing)}")

    sources = memo["sources"]
    if not isinstance(sources, list) or not sources:
        raise MemoValidationError("sources must be a non-empty list")
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("title"), str):
            raise MemoValidationError("each source needs a title and HTTPS URL")
        if not _is_https_url(source.get("url")):
            raise MemoValidationError("each source URL must use HTTPS")
    return memo


def _memo_directory(reports_dir: Path, memo_date: str | None) -> Path:
    if memo_date:
        if not DATE_PATTERN.fullmatch(memo_date):
            raise MemoValidationError("--memo-date must use YYYY-MM-DD")
        try:
            date.fromisoformat(memo_date)
        except ValueError as exc:
            raise MemoValidationError("--memo-date is not a calendar date") from exc
        candidate = reports_dir / memo_date
        if not candidate.is_dir():
            raise MemoValidationError(f"memo directory not found: {candidate}")
        return candidate

    candidates: list[tuple[date, Path]] = []
    if reports_dir.is_dir():
        for child in reports_dir.iterdir():
            if child.is_dir() and DATE_PATTERN.fullmatch(child.name):
                try:
                    candidates.append((date.fromisoformat(child.name), child))
                except ValueError:
                    continue
    if not candidates:
        raise MemoValidationError(f"no dated memo directories found under {reports_dir}")
    return max(candidates, key=lambda pair: pair[0])[1]


def bundle_memo(
    reports_dir: Path,
    memo_date: str | None,
    output_dir: Path,
    summary_file: Path | None = None,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    memo_dir = _memo_directory(reports_dir, memo_date)
    json_path = memo_dir / "memo.json"
    markdown_path = memo_dir / "memo.md"
    if not json_path.is_file() or not markdown_path.is_file():
        raise MemoValidationError(f"{memo_dir} must contain memo.json and memo.md")
    try:
        memo = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MemoValidationError(f"cannot read valid JSON from {json_path}: {exc}") from exc
    validate_memo(memo, expected_date=memo_dir.name)
    if memo_date:
        validate_memo(memo, expected_date=memo_date)
    markdown_body = markdown_path.read_text(encoding="utf-8").strip()
    if not markdown_body:
        raise MemoValidationError("memo.md must not be empty")
    if "NO_TRADE" not in markdown_body or "órdenes: 0" not in markdown_body.casefold():
        raise MemoValidationError("memo.md must state NO_TRADE and zero orders")

    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(json_path, output_dir / "memo.json")
    shutil.copyfile(markdown_path, output_dir / "memo.md")
    research_report_artifact: str | None = None
    research = memo.get("research")
    research_report = research.get("comparison_report") if isinstance(research, dict) else None
    if research_report is not None:
        if not isinstance(research_report, str) or not research_report.strip():
            raise MemoValidationError("research.comparison_report must be a repository-relative path")
        report_relative_path = Path(research_report)
        if report_relative_path.is_absolute() or ".." in report_relative_path.parts:
            raise MemoValidationError("research.comparison_report must stay inside the repository")
        repo_root = (repository_root or Path.cwd()).resolve()
        report_path = (repo_root / report_relative_path).resolve()
        if not report_path.is_relative_to(repo_root):
            raise MemoValidationError("research.comparison_report must stay inside the repository")
        if not report_path.is_file():
            raise MemoValidationError(f"research report not found: {research_report}")
        report_output_path = output_dir / report_relative_path
        report_output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(report_path, report_output_path)
        research_report_artifact = report_relative_path.as_posix()

    summary = (
        f"# Order memo — {memo['for_session_date']}\n\n"
        f"- Decision: **{memo['decision_status']}**\n"
        f"- Instruments reviewed: **{len(memo['watchlist'])}**\n"
        f"- Orders: **0**\n"
        f"- Execution: **manual only**\n"
        f"- Portfolio state verified: **no**\n"
        f"- Memo ID: `{memo['memo_id']}`\n"
    )
    if research_report_artifact:
        summary += f"- Research report: `{research_report_artifact}`\n"
    (output_dir / "summary.md").write_text(summary, encoding="utf-8")
    if summary_file is not None:
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        with summary_file.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(summary + "\n")
    return {
        "memo_id": memo["memo_id"],
        "for_session_date": memo["for_session_date"],
        "decision_status": memo["decision_status"],
        "watchlist_count": len(memo["watchlist"]),
        "order_count": len(memo["orders"]),
        "research_report": research_report_artifact,
        "bundle_dir": str(output_dir),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and bundle the latest manual-only Actinver order memo."
    )
    parser.add_argument("--reports-dir", type=Path, default=Path("reports/order_memos"))
    parser.add_argument("--memo-date", default="", help="YYYY-MM-DD; empty selects the newest memo")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary-file", type=Path, help="Append a concise summary to this file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = bundle_memo(
            args.reports_dir,
            args.memo_date or None,
            args.output_dir,
            args.summary_file,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (MemoValidationError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
