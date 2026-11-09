# Jira Health Toolkit

Scripts I used on Jira performance-tuning, cleanup, and migration engagements. I rewrote them clean from my consulting notes (2017–2023). There's no client data in here.

On a big instance, the slowdowns usually come from clutter, not hardware: hundreds of unused custom fields, abandoned workflows, and filters nobody owns anymore. This toolkit gives you a number for each of those, then shows exactly what to clean up first.

**Case study:** [Fixing a Jira instance that every dashboard said was healthy](performance-tuning/README.md). This is a real 2018 performance engagement, with client details removed. At peak, the database connection pool went from exhausted (20 of 20 connections in use) to 4 of 50, while peak reads per second more than doubled.

## What's here

| File | What it does |
| --- | --- |
| `health_check.py` | Counts 13 objects that drive performance (issues, custom fields, workflows, screens, schemes, and more). Grades each one against size thresholds and rolls them up into one GREEN / YELLOW / RED rating. |
| `thresholds.example.json` | Healthy, medium-risk, and high-risk limits for a single-node Jira Server. These are starting points, so tune them for your setup. |
| `inventory_queries.sql` | The detail behind each count. Every custom field, project, issue type, workflow, status, and filter, with its issue count and last activity date. |
| `bulk_user_update.py` | Fixes user display names and emails from a CSV through the Jira REST API, for migrations and directory merges. |

## How I used it on an engagement

1. **Measure.** Run `health_check.py` against a staging copy of the database to get the overall rating and the worst offenders.
2. **Inventory.** Run the matching queries in `inventory_queries.sql`. Sort by issue count and last activity. Anything with zero issues, or no activity in a year or more, is a cleanup candidate.
3. **Check dependencies.** Before you delete a filter, run queries 7 and 8. Filters behind boards and dashboards break things when they disappear.
4. **Clean up, then measure again.** Re-run the health check to show the before-and-after difference.

## Usage

```bash
pip install -r requirements.txt   # plus your DB driver: pyodbc or psycopg2-binary

# Health check (read-only: SELECT COUNT(*) only)
export JIRA_DB_URL="postgresql+psycopg2://readonly:***@db-host/jiradb"
python health_check.py
python health_check.py --json > health.json

# Bulk user update (dry run until you pass --apply)
export JIRA_URL=https://jira.example.com JIRA_USER=admin JIRA_TOKEN=***
python bulk_user_update.py users.example.csv
python bulk_user_update.py users.example.csv --apply
```

Example output:

```
Metric                         Count  Band        Healthy / Medium / High limits
------------------------------------------------------------------------------
screens                          257  high        50 / 200 / 800
issues                       400,000  medium      150,000 / 500,000 / 2,000,000
custom_fields                    328  medium      250 / 500 / 1,500
workflows                        128  medium      80 / 150 / 600
...
------------------------------------------------------------------------------
Overall instance health: RED
```

## Design choices

- **Read-only by default.** The health check only runs `COUNT(*)`. The user updater only previews changes until you pass `--apply`.
- **No secrets in code.** Credentials come from environment variables, and TLS verification stays on unless you explicitly turn it off.
- **Fails soft.** If one table is missing on an older Jira version, the health check skips that metric and reports the rest.

Tested against the standard Jira Server / Data Center schema (7.x–8.x). The SQL is written for SQL Server, and the header of `inventory_queries.sql` lists the PostgreSQL changes.

## License

MIT
