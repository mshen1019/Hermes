#!/usr/bin/env python3
"""
Apply to jobs from Argus job_results directory using Hermes.

This script processes job listings organized by company and applies to them
using the Hermes job application automation system.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

# Load environment variables
load_dotenv()

# Import Hermes modules
from hermes.browser import BrowserManager
from hermes.config import Profile, load_profile
from hermes.llm_helper import LLMHelper
from hermes.logger import ApplicationLogger
from run import process_job

console = Console()


def find_company_directories(argus_dir: Path) -> List[Path]:
    """
    Find all company directories in the Argus job_results structure.

    Structure: argus_dir/YYYY-MM-DD/CompanyName/jobs.json

    Returns:
        List of company directories containing jobs.json files
    """
    company_dirs = []

    if not argus_dir.exists():
        console.print(f"[red]Error:[/red] Directory not found: {argus_dir}")
        return []

    # Find all date directories
    for date_dir in sorted(argus_dir.iterdir()):
        if not date_dir.is_dir() or not date_dir.name.startswith("202"):
            continue

        # Find all company directories within each date
        for company_dir in sorted(date_dir.iterdir()):
            if not company_dir.is_dir():
                continue

            jobs_file = company_dir / "jobs.json"
            if jobs_file.exists():
                company_dirs.append(company_dir)

    return company_dirs


def load_jobs_from_file(jobs_file: Path) -> List[Dict]:
    """Load jobs from a jobs.json file."""
    try:
        with open(jobs_file, 'r') as f:
            jobs = json.load(f)
        return jobs if isinstance(jobs, list) else []
    except Exception as e:
        console.print(f"[red]Error loading {jobs_file}:[/red] {e}")
        return []


def display_company_summary(company_dirs: List[Path]) -> None:
    """Display a summary table of companies and job counts."""
    table = Table(title="Companies with Job Listings", show_header=True)
    table.add_column("Company", style="cyan")
    table.add_column("Date", style="dim")
    table.add_column("Jobs", justify="right", style="green")

    total_jobs = 0
    for company_dir in company_dirs:
        jobs_file = company_dir / "jobs.json"
        jobs = load_jobs_from_file(jobs_file)
        job_count = len(jobs)
        total_jobs += job_count

        table.add_row(
            company_dir.name,
            company_dir.parent.name,
            str(job_count)
        )

    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {len(company_dirs)} companies, {total_jobs} jobs")


async def process_company(
    company_dir: Path,
    browser: BrowserManager,
    profile: Profile,
    profile_name: str,
    llm: LLMHelper,
    logger: ApplicationLogger,
    auto_submit: bool = False,
    max_jobs: Optional[int] = None,
) -> Dict[str, int]:
    """
    Process all jobs for a single company.

    Returns:
        Dict with success/failure counts
    """
    company_name = company_dir.name
    jobs_file = company_dir / "jobs.json"

    jobs = load_jobs_from_file(jobs_file)

    if not jobs:
        console.print(f"[yellow]No jobs found for {company_name}[/yellow]")
        return {"success": 0, "failed": 0, "skipped": 0}

    # Limit number of jobs if specified
    if max_jobs and len(jobs) > max_jobs:
        console.print(f"[dim]Limiting to first {max_jobs} jobs out of {len(jobs)} total[/dim]")
        jobs = jobs[:max_jobs]

    console.print()
    console.print(Panel(
        f"[bold]{company_name}[/bold]\n"
        f"Processing {len(jobs)} job(s)",
        style="blue"
    ))

    stats = {"success": 0, "failed": 0, "skipped": 0}

    for i, job in enumerate(jobs, 1):
        console.print(f"\n[bold cyan]Job {i}/{len(jobs)}:[/bold cyan] {job.get('title', 'Unknown')}")

        success = await process_job(
            browser=browser,
            profile=profile,
            profile_name=profile_name,
            llm=llm,
            logger=logger,
            job=job,
            auto_submit=auto_submit,
            browser_confirm_only=True,  # Automatically detect submission via URL change
        )

        if success:
            stats["success"] += 1
        else:
            stats["failed"] += 1

        # Small delay between jobs
        if i < len(jobs):
            await asyncio.sleep(3)

    console.print()
    console.print(Panel(
        f"[bold]{company_name} Complete[/bold]\n"
        f"✓ Success: {stats['success']}\n"
        f"✗ Failed: {stats['failed']}",
        style="green" if stats["success"] > 0 else "yellow"
    ))

    return stats


async def main(
    argus_dir: str,
    profile_name: Optional[str] = None,
    profile_path: Optional[str] = None,
    cdp_url: str = "http://localhost:9222",
    auto_submit: bool = False,
    companies: Optional[List[str]] = None,
    max_jobs_per_company: Optional[int] = None,
    interactive: bool = False,
):
    """Main entry point."""

    argus_path = Path(argus_dir)

    # Find all company directories
    console.print("[dim]Scanning for company directories...[/dim]")
    company_dirs = find_company_directories(argus_path)

    if not company_dirs:
        console.print("[red]No company directories found![/red]")
        return 1

    # Filter by company names if specified
    if companies:
        company_dirs = [
            d for d in company_dirs
            if d.name in companies or d.name.replace("_", " ") in companies
        ]
        if not company_dirs:
            console.print(f"[red]No matching companies found for: {companies}[/red]")
            return 1

    # Display summary
    display_company_summary(company_dirs)

    # Confirm before starting
    if interactive:
        console.print()
        if not Confirm.ask(
            f"[bold]Start applying to {len(company_dirs)} companies?[/bold]",
            default=False
        ):
            console.print("Cancelled.")
            return 0

    # Load profile
    try:
        profile = load_profile(profile_name=profile_name, config_path=profile_path)
        display_name = profile_name or (profile_path if profile_path else "default")
        console.print(f"[green]✓[/green] Profile loaded: [bold]{display_name}[/bold]")
    except FileNotFoundError as e:
        console.print(f"[red]Error loading profile:[/red] {e}")
        return 1

    # Initialize LLM helper
    llm = LLMHelper(profile)
    if llm.is_available():
        console.print("[green]✓[/green] LLM helper available")
    else:
        console.print("[yellow]⚠[/yellow] LLM helper not available (set ANTHROPIC_API_KEY)")

    # Initialize logger
    logger = ApplicationLogger()
    console.print(f"[green]✓[/green] Logging to {logger.session_dir}")

    # Connect to browser
    console.print(f"[dim]Connecting to Chrome at {cdp_url}...[/dim]")

    try:
        async with BrowserManager(cdp_url) as browser:
            console.print("[green]✓[/green] Connected to Chrome")

            total_stats = {"success": 0, "failed": 0, "skipped": 0}

            # Process each company
            for i, company_dir in enumerate(company_dirs, 1):
                console.print(f"\n[bold]Company {i}/{len(company_dirs)}[/bold]")

                # Ask for confirmation before each company if interactive
                if interactive and i > 1:
                    console.print()
                    if not Confirm.ask(
                        f"Continue to next company ({company_dir.name})?",
                        default=True
                    ):
                        console.print("[yellow]Stopping at user request[/yellow]")
                        break

                stats = await process_company(
                    company_dir=company_dir,
                    browser=browser,
                    profile=profile,
                    profile_name=display_name,
                    llm=llm,
                    logger=logger,
                    auto_submit=auto_submit,
                    max_jobs=max_jobs_per_company,
                )

                # Update totals
                for key in total_stats:
                    total_stats[key] += stats[key]

                # Delay between companies
                if i < len(company_dirs):
                    await asyncio.sleep(5)

            # Print final report
            console.print("\n" + "=" * 60)
            console.print(Panel(
                f"[bold]Session Complete[/bold]\n\n"
                f"Companies: {i}/{len(company_dirs)}\n"
                f"✓ Success: {total_stats['success']}\n"
                f"✗ Failed: {total_stats['failed']}\n"
                f"Total Applications: {total_stats['success'] + total_stats['failed']}",
                style="green" if total_stats['success'] > 0 else "yellow"
            ))
            console.print(logger.get_session_report())

    except ConnectionError as e:
        console.print(f"[red]Browser connection failed:[/red] {e}")
        console.print("\n[yellow]Make sure Chrome is running with debugging enabled:[/yellow]")
        console.print('  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome '
                     '--remote-debugging-port=9222 --user-data-dir=/tmp/chrome-hermes')
        return 1

    return 0


def cli():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Apply to jobs from Argus directory using Hermes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Apply to all companies
  python apply_argus_jobs.py /path/to/Argus/job_results/Ming --profile Ming

  # Apply to specific companies only
  python apply_argus_jobs.py /path/to/Argus/job_results/Ming --profile Ming --companies Google Anthropic

  # Limit jobs per company (for testing)
  python apply_argus_jobs.py /path/to/Argus/job_results/Ming --profile Ming --max-jobs 3

  # Interactive mode with confirmations
  python apply_argus_jobs.py /path/to/Argus/job_results/Ming --profile Ming --interactive

  # Auto-pilot mode (not recommended)
  python apply_argus_jobs.py /path/to/Argus/job_results/Ming --profile Ming --auto-pilot
        """
    )

    parser.add_argument(
        "argus_dir",
        help="Path to Argus job_results directory (e.g., /path/to/Argus/job_results/Ming)"
    )
    parser.add_argument(
        "--profile", "-p",
        help="Profile name (e.g., 'Ming')",
        dest="profile_name",
    )
    parser.add_argument(
        "--profile-path",
        help="Direct path to profile YAML file (overrides --profile)",
        dest="profile_path",
    )
    parser.add_argument(
        "--cdp-url",
        default="http://localhost:9222",
        help="Chrome DevTools Protocol URL (default: http://localhost:9222)",
    )
    parser.add_argument(
        "--auto-pilot",
        action="store_true",
        help="Auto-submit after filling (use with caution)",
        dest="auto_submit",
    )
    parser.add_argument(
        "--companies", "-c",
        nargs="+",
        help="Only apply to specific companies (e.g., --companies Google Anthropic)",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        help="Maximum jobs to apply to per company (useful for testing)",
        dest="max_jobs_per_company",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Ask for confirmation before each company",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all companies and exit (no applications)",
        dest="list_only",
    )

    args = parser.parse_args()

    # Handle --list
    if args.list_only:
        argus_path = Path(args.argus_dir)
        company_dirs = find_company_directories(argus_path)
        if company_dirs:
            display_company_summary(company_dirs)
        return 0

    # Validate required arguments
    if not args.profile_name and not args.profile_path:
        parser.error("--profile or --profile-path is required")

    return asyncio.run(main(
        argus_dir=args.argus_dir,
        profile_name=args.profile_name,
        profile_path=args.profile_path,
        cdp_url=args.cdp_url,
        auto_submit=args.auto_submit,
        companies=args.companies,
        max_jobs_per_company=args.max_jobs_per_company,
        interactive=args.interactive,
    ))


if __name__ == "__main__":
    sys.exit(cli())
