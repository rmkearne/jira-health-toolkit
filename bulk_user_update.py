#!/usr/bin/env python3
"""
Bulk-update Jira user display names and email addresses from a CSV.

Built for migrations and merges, where users arrive from another directory
with stale names or emails and need fixing in one pass before cutover.

CSV format (no header): username,display_name,email
    jdoe,Jane Doe,jane.doe@example.com

Dry run by default. Nothing changes until you pass --apply.

Usage:
    export JIRA_URL=https://jira.example.com
    export JIRA_USER=admin
    export JIRA_TOKEN=...            # password or personal access token
    python bulk_user_update.py users.csv            # dry run
    python bulk_user_update.py users.csv --apply    # make the changes
"""

import argparse
import csv
import os
import sys

import requests


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        for lineno, row in enumerate(csv.reader(fh), start=1):
            if not row or row[0].startswith("#"):
                continue
            if len(row) != 3:
                print(f"line {lineno}: expected 3 columns, got {len(row)} -- skipped", file=sys.stderr)
                continue
            yield lineno, [cell.strip() for cell in row]


def main():
    parser = argparse.ArgumentParser(description="Bulk-update Jira user names and emails from a CSV.")
    parser.add_argument("csv_path")
    parser.add_argument("--apply", action="store_true", help="actually send the updates (default is a dry run)")
    parser.add_argument("--insecure", action="store_true", help="skip TLS verification (test instances only)")
    args = parser.parse_args()

    base_url = os.environ.get("JIRA_URL", "").rstrip("/")
    user, token = os.environ.get("JIRA_USER"), os.environ.get("JIRA_TOKEN")
    if not (base_url and user and token):
        sys.exit("Set JIRA_URL, JIRA_USER and JIRA_TOKEN.")

    session = requests.Session()
    session.auth = (user, token)
    session.headers["Content-Type"] = "application/json"
    session.verify = not args.insecure

    updated = failed = 0
    for lineno, (username, display_name, email) in load_rows(args.csv_path):
        payload = {"displayName": display_name, "emailAddress": email}
        if not args.apply:
            print(f"[dry run] {username}: {payload}")
            continue
        resp = session.put(f"{base_url}/rest/api/2/user", params={"username": username}, json=payload, timeout=30)
        if resp.ok:
            updated += 1
        else:
            failed += 1
            print(f"line {lineno} {username}: HTTP {resp.status_code} {resp.text[:200]}", file=sys.stderr)

    if args.apply:
        print(f"Done. {updated} updated, {failed} failed.")
    else:
        print("Dry run only. Re-run with --apply to make these changes.")


if __name__ == "__main__":
    main()
