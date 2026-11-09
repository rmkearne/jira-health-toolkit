#!/usr/bin/env python3
"""
Jira instance health check.

Counts the objects that drive Jira performance (issues, custom fields,
workflows, screens, schemes, ...) straight from the Jira database, then grades
each one against size thresholds and rolls the result up to GREEN / YELLOW / RED.

Read-only: every statement is a SELECT COUNT(*).

Usage:
    export JIRA_DB_URL="mssql+pyodbc://user:pass@host/jiradb?driver=ODBC+Driver+18+for+SQL+Server"
    python health_check.py                       # uses thresholds.example.json
    python health_check.py --thresholds my.json  # your own thresholds
    python health_check.py --json                # machine-readable output
"""

import argparse
import json
import os
import sys

from sqlalchemy import create_engine, text

# One COUNT per metric. Table names follow the standard Jira Server / Data
# Center schema. Run inventory_queries.sql for the detail behind each number.
COUNT_QUERIES = {
    "issues": "SELECT COUNT(*) FROM jiraissue",
    "projects": "SELECT COUNT(*) FROM project",
    "users": "SELECT COUNT(*) FROM cwd_user",
    "groups": "SELECT COUNT(*) FROM cwd_group",
    "custom_fields": "SELECT COUNT(*) FROM customfield",
    "workflows": "SELECT COUNT(*) FROM jiraworkflows",
    "comments": "SELECT COUNT(*) FROM jiraaction WHERE actiontype = 'comment'",
    "permission_schemes": "SELECT COUNT(*) FROM permissionscheme",
    "issue_security_schemes": "SELECT COUNT(*) FROM issuesecurityscheme",
    "screens": "SELECT COUNT(*) FROM fieldscreen",
    "screen_schemes": "SELECT COUNT(*) FROM fieldscreenscheme",
    "issue_types": "SELECT COUNT(*) FROM issuetype",
    "statuses": "SELECT COUNT(*) FROM issuestatus",
}

BANDS = ["healthy", "medium", "high", "extra_large"]
ROLLUP = {"healthy": "GREEN", "medium": "YELLOW", "high": "RED", "extra_large": "RED"}


def band_for(value, limits):
    """Return the band a count falls into. limits = [healthy_max, medium_max, high_max]."""
    healthy_max, medium_max, high_max = limits
    if value <= healthy_max:
        return "healthy"
    if value <= medium_max:
        return "medium"
    if value <= high_max:
        return "high"
    return "extra_large"


def collect_counts(conn):
    counts, errors = {}, {}
    for metric, sql in COUNT_QUERIES.items():
        try:
            counts[metric] = conn.execute(text(sql)).scalar_one()
        except Exception as exc:  # a missing table shouldn't kill the whole report
            errors[metric] = str(exc).splitlines()[0]
    return counts, errors


def grade(counts, thresholds):
    rows = []
    for metric, value in counts.items():
        limits = thresholds.get(metric)
        if limits is None:
            continue
        rows.append({"metric": metric, "count": value, "band": band_for(value, limits), "limits": limits})
    worst = max((BANDS.index(r["band"]) for r in rows), default=0)
    return rows, ROLLUP[BANDS[worst]]


def print_report(rows, overall, errors):
    print(f"{'Metric':<24}{'Count':>12}  {'Band':<12}Healthy / Medium / High limits")
    print("-" * 78)
    for r in sorted(rows, key=lambda r: BANDS.index(r["band"]), reverse=True):
        h, m, hi = r["limits"]
        print(f"{r['metric']:<24}{r['count']:>12,}  {r['band']:<12}{h:,} / {m:,} / {hi:,}")
    for metric, err in errors.items():
        print(f"{metric:<24}{'n/a':>12}  skipped     {err}")
    print("-" * 78)
    print(f"Overall instance health: {overall}")


def main():
    parser = argparse.ArgumentParser(description="Grade a Jira instance against size thresholds.")
    parser.add_argument("--db-url", default=os.environ.get("JIRA_DB_URL"),
                        help="SQLAlchemy URL for the Jira database (or set JIRA_DB_URL)")
    parser.add_argument("--thresholds", default=os.path.join(os.path.dirname(__file__), "thresholds.example.json"))
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args()

    if not args.db_url:
        sys.exit("Set JIRA_DB_URL or pass --db-url.")

    with open(args.thresholds) as fh:
        thresholds = {k: v for k, v in json.load(fh).items() if not k.startswith("_")}

    engine = create_engine(args.db_url)
    with engine.connect() as conn:
        counts, errors = collect_counts(conn)

    rows, overall = grade(counts, thresholds)
    if args.json:
        print(json.dumps({"overall": overall, "metrics": rows, "skipped": errors}, indent=2))
    else:
        print_report(rows, overall, errors)


if __name__ == "__main__":
    main()
