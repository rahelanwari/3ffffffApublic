#!/usr/bin/env python3
import argparse
import datetime as dt
import sqlite3
import socket
import psutil
from pathlib import Path
from typing import List

DEFAULT_DB = Path("metrics.db")
ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"

KNOWN_METRICS = {
    "cpu-usage": lambda: float(psutil.cpu_percent(interval=0.1)),
    "memory-usage": lambda: float(psutil.virtual_memory().percent),
    "disk-0-usage": lambda: float(psutil.disk_usage("/").percent),
}

def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)

def isoformat_utc(t: dt.datetime) -> str:
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    else:
        t = t.astimezone(dt.timezone.utc)
    return t.strftime(ISO_FMT)

def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sample (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            ts     TEXT    NOT NULL,
            host   TEXT    NOT NULL,
            ip     TEXT    NOT NULL,
            metric TEXT    NOT NULL,
            value  REAL    NOT NULL
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sample_host_metric_ts ON sample(host, metric, ts);"
    )

def insert_sample(conn: sqlite3.Connection, ts: str, host: str, ip: str, metric: str, value: float):
    conn.execute(
        "INSERT INTO sample (ts, host, ip, metric, value) VALUES (?, ?, ?, ?, ?);",
        (ts, host, ip, metric, value),
    )

def cmd_init(args):
    conn = open_db(Path(args.db))
    init_db(conn)
    print(f"Database initialized at {args.db}")

def cmd_measure(args):
    conn = open_db(Path(args.db))
    init_db(conn)

    host = socket.gethostname()
    ip = socket.gethostbyname(host)
    ts = isoformat_utc(utcnow())

    for metric in args.metrics:
        if metric not in KNOWN_METRICS:
            print(f"Unknown metric: {metric}")
            continue
        value = KNOWN_METRICS[metric]()
        insert_sample(conn, ts, host, ip, metric, value)
        if args.verbose:
            print(f"{ts} | {host} | {ip} | {metric} | {value:.2f}")

def cmd_show(args):
    conn = open_db(Path(args.db))
    sql = "SELECT ts, host, ip, metric, value FROM sample WHERE 1=1"
    params: List[str] = []

    if args.metric:
        sql += " AND metric = ?"
        params.append(args.metric)

    if args.start:
        start_time = parse_relative_time(args.start)
        sql += " AND ts >= ?"
        params.append(isoformat_utc(start_time))

    if args.end:
        end_time = parse_relative_time(args.end)
        sql += " AND ts <= ?"
        params.append(isoformat_utc(end_time))

    sql += " ORDER BY ts DESC"
    if args.limit:
        sql += " LIMIT ?"
        params.append(args.limit)

    rows = conn.execute(sql, params).fetchall()
    for r in rows:
        print(f"{r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]:.2f}")

    if args.average and rows:
        values = [r[4] for r in rows]
        avg = sum(values) / len(values)
        print(f"\nAverage {args.metric}: {avg:.2f}")

def cmd_export(args):
    import csv
    conn = open_db(Path(args.db))
    rows = conn.execute("SELECT ts, host, ip, metric, value FROM sample").fetchall()

    with open(args.out, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "host", "ip", "metric", "value"])
        writer.writerows(rows)

    print(f"Exported {len(rows)} rows to {args.out}")

def cmd_prune(args):
    conn = open_db(Path(args.db))
    cutoff = isoformat_utc(utcnow() - dt.timedelta(days=args.retention_days))
    deleted = conn.execute("DELETE FROM sample WHERE ts < ?;", (cutoff,)).rowcount
    print(f"Deleted {deleted} rows older than {args.retention_days} days")

    if args.vacuum:
        conn.execute("VACUUM;")
        print("Database vacuumed")

def parse_relative_time(s: str) -> dt.datetime:
    if s.startswith("-") and s[-1] in "hdm":
        num = int(s[1:-1])
        if s.endswith("h"):
            return utcnow() - dt.timedelta(hours=num)
        if s.endswith("d"):
            return utcnow() - dt.timedelta(days=num)
        if s.endswith("m"):
            return utcnow() - dt.timedelta(minutes=num)
    return dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc)

def build_parser():
    p = argparse.ArgumentParser(description="Monitoring CLI with SQLite storage")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init-db", help="Initialize the database")
    sp.set_defaults(func=cmd_init)

    m = sub.add_parser("measure", help="Collect metrics")
    m.add_argument("--metrics", nargs="+", required=True, help=f"Choose from: {', '.join(KNOWN_METRICS)}")
    m.add_argument("-v", "--verbose", action="store_true")
    m.set_defaults(func=cmd_measure)

    s = sub.add_parser("show", help="Show collected metrics")
    s.add_argument("--metric", help="Filter by metric")
    s.add_argument("--start", help="Start time (e.g. -1h, -2d)")
    s.add_argument("--end", help="End time")
    s.add_argument("--limit", type=int, help="Limit number of rows")
    s.add_argument("--average", action="store_true", help="Calculate average value")
    s.set_defaults(func=cmd_show)

    e = sub.add_parser("export", help="Export all data to CSV")
    e.add_argument("--out", required=True, help="Output CSV file")
    e.set_defaults(func=cmd_export)

    pr = sub.add_parser("prune", help="Prune old data")
    pr.add_argument("--retention-days", type=int, required=True)
    pr.add_argument("--vacuum", action="store_true")
    pr.set_defaults(func=cmd_prune)

    return p

def main():
    args = build_parser().parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
