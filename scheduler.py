"""Daily pipeline scheduler.

Orchestrates the full daily pipeline. Designed to run at 7am AEST
via Windows Task Scheduler.

Setup (Windows Task Scheduler):
  1. Open Task Scheduler
  2. Create Basic Task -> "Recruiter Pipeline"
  3. Trigger: Daily at 7:00 AM
  4. Action: Start a Program
     Program: D:\Recuriting Tool\.venv\Scripts\python.exe
     Arguments: main.py run-all
     Start in: D:\Recuriting Tool
  5. For Monday weekly summary, create a second task:
     Trigger: Weekly on Monday at 7:00 AM
     Arguments: main.py weekly-summary

Can also be run manually: python scheduler.py
"""

import sys
from datetime import datetime, timezone


def run_daily():
    """Run the full daily pipeline."""
    print(f"\n{'#' * 60}")
    print(f"  DAILY PIPELINE — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'#' * 60}\n")

    from pipeline.discover import run_discovery
    from pipeline.enrich import run_enrichment
    from pipeline.callsheet import run_callsheet

    try:
        print("STEP 1: Discovering new companies...")
        run_discovery()
    except Exception as e:
        print(f"Discovery error: {e}")

    try:
        print("\nSTEP 2: Enriching contacts...")
        run_enrichment()
    except Exception as e:
        print(f"Enrichment error: {e}")

    try:
        print("\nSTEP 3: Generating call sheet with openers...")
        run_callsheet(with_openers=True)
    except Exception as e:
        print(f"Call sheet error: {e}")

    # Run warmup on weekdays
    weekday = datetime.now(timezone.utc).weekday()
    if weekday < 5:  # Monday-Friday
        try:
            print("\nSTEP 4: Generating LinkedIn warm-up messages...")
            from pipeline.warmup import run_warmup
            run_warmup(limit=5)
        except Exception as e:
            print(f"Warmup error: {e}")

    # Run monitoring weekly (Wednesdays)
    if weekday == 2:
        try:
            print("\nSTEP 5: Running company monitoring...")
            from pipeline.monitor import run_monitor
            run_monitor()
        except Exception as e:
            print(f"Monitor error: {e}")

    print(f"\n{'#' * 60}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'#' * 60}")


def run_weekly():
    """Run the weekly summary (Mondays)."""
    from pipeline.weekly_summary import run_weekly_summary
    run_weekly_summary()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "weekly":
        run_weekly()
    else:
        run_daily()
