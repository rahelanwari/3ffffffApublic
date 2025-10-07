#!/usr/bin/env python3
"""
Task 10 - Monitoring CLI (non-interactive)
Modes:
  measure -> meet metrics en append naar CSV
  show    -> filter/laat zien en bereken avg/sum
Append-only, tenzij --reset.
"""

import argparse
import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import psutil

DEFAULT_DB = Path("metrics.csv")
TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"

# ---------- Metric functions ----------
def metric_cpu_usage() -> float:
    return float(psutil.cpu_percent(interval=0.1))

def metric_mem_usage() -> float:
    return float(psutil.virtual_memory().percent)

def metric_disk0_usage() -> float:
    return float(psutil.disk_usage("/").percent)

KNOWN_METRICS = {
    "cpu-usage": metric_cpu_usage,
    "memory-usage": metric_mem_usage,
    "disk-0-usage": metric_disk0_usage,
}

# ---------- Data structures ----------
@dataclass(frozen=True)
class Sample:
    timestamp: dt.datetime
    metric: str
    value: float

    def as_row(self) -> Tuple[str, str, str]:
        return (self.timestamp.strftime(TIMESTAMP_FMT), self.metric, f"{self.value:.3f}")

# ---------- CSV storage helpers ----------
def ensure_header(file: Path) -> None:
    if not file.exists() or file.stat().st_size == 0:
        with file.open("w", newline="") as f:
            csv.writer(f).writerow(["timestamp", "metric", "value"])

def append_samples(file: Path, samples: List[Sample]) -> None:
    ensure_header(file)
    with file.open("a", newline="") as f:
        w = csv.writer(f)
        for s in samples:
            w.writerow(s.as_row())

def read_samples(file: Path) -> List[Sample]:
    if not file.exists() or file.stat().st_size == 0:
        return []
    out: List[Sample] = []
    with file.open("r", newline="") as f:
        for row in csv.DictReader(f):
            try:
                ts = dt.datetime.strptime(row["timestamp"], TIMESTAMP_FMT)
                out.append(Sample(ts, row["metric"], float(row["value"])))
            except Exception:
                continue
    return out

# ---------- Filtering & formatting ----------
def parse_time(s: Optional[str]) -> Optional[dt.datetime]:
    if not s:
        return None
    for fmt in (TIMESTAMP_FMT, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError("Use e.g. 2025-09-27T15:30:00 or 2025-09-27")

def filter_samples(items: List[Sample], metric: Optional[str],
                   start: Optional[dt.datetime], end: Optional[dt.datetime]) -> List[Sample]:
    res = []
    for s in items:
        if metric and s.metric != metric:
            continue
        if start and s.timestamp < start:
            continue
        if end and s.timestamp > end:
            continue
        res.append(s)
    return res

def fmt_table(rows: List[Tuple[str, str, str]]) -> str:
    cols = ["timestamp", "metric", "value"]
    widths = [max(len(cols[i]), max((len(r[i]) for r in rows), default=0)) for i in range(3)]
    header = " | ".join(cols[i].ljust(widths[i]) for i in range(3))
    sep = "-+-".join("-" * w for w in widths)
    body = "\n".join(" | ".join(r[i].ljust(widths[i]) for i in range(3)) for r in rows)
    return f"{header}\n{sep}\n{body}" if rows else "(no data)"

# ---------- Commands ----------
def cmd_measure(args: argparse.Namespace) -> None:
    db = Path(args.db)
    if args.reset and db.exists():
        db.unlink(missing_ok=True)

    unknown = [m for m in args.metrics if m not in KNOWN_METRICS]
    if unknown:
        raise SystemExit(f"Unknown: {', '.join(unknown)}. Known: {', '.join(KNOWN_METRICS)}")

    now = dt.datetime.now()
    samples = [Sample(now, m, KNOWN_METRICS[m]()) for m in args.metrics]
    append_samples(db, samples)

    if args.verbose:
        print(fmt_table([s.as_row() for s in samples]))

def cmd_show(args: argparse.Namespace) -> None:
    items = read_samples(Path(args.db))
    data = filter_samples(items, args.metric, parse_time(args.start), parse_time(args.end))
    print(fmt_table([s.as_row() for s in data]))

    if args.average and data:
        avg = sum(s.value for s in data) / len(data)
        print(f"\nAverage({args.metric or 'ALL'}) = {avg:.3f}")
    if args.total and data:
        total = sum(s.value for s in data)
        print(f"Total({args.metric or 'ALL'}) = {total:.3f}")

# ---------- CLI ----------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Task 10 Monitoring CLI")
    p.add_argument("--db", default=str(DEFAULT_DB), help=f"CSV path (default: {DEFAULT_DB})")
    sub = p.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("measure", help="Collect metrics now and append to CSV")
    m.add_argument("--metrics", nargs="+", required=True,
                   help=f"Choose from: {', '.join(KNOWN_METRICS)}")
    m.add_argument("--reset", action="store_true", help="Delete CSV before appending")
    m.add_argument("-v", "--verbose", action="store_true")
    m.set_defaults(func=cmd_measure)

    s = sub.add_parser("show", help="Read CSV, filter/time window, show stats")
    s.add_argument("--metric", help="Filter to one metric (e.g. cpu-usage)")
    s.add_argument("--start", help="Start time (e.g. 2025-09-27T15:00:00)")
    s.add_argument("--end", help="End time   (e.g. 2025-09-27T16:00:00)")
    s.add_argument("--average", action="store_true")
    s.add_argument("--total", action="store_true")
    s.set_defaults(func=cmd_show)

    return p

def main() -> None:
    args = build_parser().parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
