#!/usr/bin/env python3
"""
Generate custom company lists from Argus job results.

Helps you create targeted application batches by filtering companies.
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict

from rich.console import Console
from rich.table import Table

console = Console()


def find_companies(argus_dir: Path) -> List[Dict]:
    """Find all companies with their job counts."""
    companies = []

    if not argus_dir.exists():
        return []

    for date_dir in sorted(argus_dir.iterdir()):
        if not date_dir.is_dir() or not date_dir.name.startswith("202"):
            continue

        for company_dir in sorted(date_dir.iterdir()):
            if not company_dir.is_dir():
                continue

            jobs_file = company_dir / "jobs.json"
            if jobs_file.exists():
                try:
                    with open(jobs_file) as f:
                        jobs = json.load(f)
                    companies.append({
                        "name": company_dir.name,
                        "date": date_dir.name,
                        "job_count": len(jobs),
                        "jobs": jobs
                    })
                except Exception:
                    pass

    return companies


def filter_companies(
    companies: List[Dict],
    min_jobs: int = 0,
    max_jobs: int = 999,
    keywords: List[str] = None,
    exclude: List[str] = None,
) -> List[Dict]:
    """Filter companies by criteria."""

    filtered = []

    for company in companies:
        # Filter by job count
        if not (min_jobs <= company["job_count"] <= max_jobs):
            continue

        # Filter by keywords in job titles
        if keywords:
            match = False
            for job in company["jobs"]:
                title = job.get("title", "").lower()
                if any(kw.lower() in title for kw in keywords):
                    match = True
                    break
            if not match:
                continue

        # Exclude companies
        if exclude and company["name"] in exclude:
            continue

        filtered.append(company)

    return filtered


def display_companies(companies: List[Dict], show_jobs: bool = False):
    """Display companies in a table."""

    if not companies:
        console.print("[yellow]No companies match the criteria[/yellow]")
        return

    table = Table(title="Filtered Companies", show_header=True)
    table.add_column("Company", style="cyan")
    table.add_column("Jobs", justify="right", style="green")

    if show_jobs:
        table.add_column("Sample Jobs", style="dim")

    total_jobs = 0

    for company in companies:
        total_jobs += company["job_count"]

        row = [company["name"], str(company["job_count"])]

        if show_jobs:
            sample = ", ".join([
                job.get("title", "")[:50]
                for job in company["jobs"][:2]
            ])
            row.append(sample)

        table.add_row(*row)

    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {len(companies)} companies, {total_jobs} jobs")


def main():
    parser = argparse.ArgumentParser(
        description="Filter and list companies from Argus job results"
    )

    parser.add_argument(
        "argus_dir",
        help="Path to Argus job_results directory"
    )
    parser.add_argument(
        "--min-jobs",
        type=int,
        default=0,
        help="Minimum jobs per company"
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=999,
        help="Maximum jobs per company"
    )
    parser.add_argument(
        "--keywords", "-k",
        nargs="+",
        help="Filter by keywords in job titles (e.g., 'ML' 'Research' 'Senior')"
    )
    parser.add_argument(
        "--exclude", "-x",
        nargs="+",
        help="Exclude specific companies"
    )
    parser.add_argument(
        "--show-jobs",
        action="store_true",
        help="Show sample job titles"
    )
    parser.add_argument(
        "--output",
        help="Output company names to file (one per line)"
    )
    parser.add_argument(
        "--category",
        choices=["ai", "bigtech", "fintech", "startup", "all"],
        help="Predefined category filter"
    )

    args = parser.parse_args()

    # Load companies
    companies = find_companies(Path(args.argus_dir))

    if not companies:
        console.print("[red]No companies found[/red]")
        return 1

    # Apply category filter
    if args.category:
        categories = {
            "ai": ["Anthropic", "OpenAI", "DeepMind", "xAI", "Mistral_AI",
                   "Perplexity_AI", "Scale_AI"],
            "bigtech": ["Google", "Meta", "Amazon", "Microsoft", "Apple"],
            "fintech": ["Stripe", "Plaid", "Coinbase", "Block", "Brex", "SoFi"],
            "startup": ["Databricks", "Snowflake", "Confluent", "MongoDB"],
        }

        if args.category == "all":
            selected = None
        else:
            selected = categories[args.category]
            companies = [c for c in companies if c["name"] in selected]

    # Filter companies
    filtered = filter_companies(
        companies,
        min_jobs=args.min_jobs,
        max_jobs=args.max_jobs,
        keywords=args.keywords,
        exclude=args.exclude,
    )

    # Display
    display_companies(filtered, show_jobs=args.show_jobs)

    # Output to file
    if args.output:
        with open(args.output, 'w') as f:
            for company in filtered:
                f.write(f"{company['name']}\n")
        console.print(f"\n[green]Saved to {args.output}[/green]")
        console.print(f"[dim]Use with: python3 apply_argus_jobs.py ... --companies $(cat {args.output})[/dim]")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
