#!/usr/bin/env python3
"""
Hermes - Job Application Automation Agent

Main entry point for running the job application automation.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from hermes.ats_detector import ATSType, detect_ats
from hermes.browser import BrowserManager
from hermes.config import Profile, load_profile, get_available_profiles
from hermes.confirmation import ConfirmationUI, review_and_confirm
from playwright.async_api import Page
from hermes.form_filler import FormFiller
from hermes.llm_helper import LLMHelper
from hermes.logger import ApplicationLogger, ApplicationStatus


console = Console()

# Common "Apply" button selectors and text patterns
APPLY_BUTTON_SELECTORS = [
    # Airbnb specific
    '.apply-btn',
    'button.apply-btn',
    # Greenhouse specific (prioritize these)
    '#grnhse_app iframe',  # Greenhouse embedded iframe
    'a[href*="boards.greenhouse.io"]',
    'a[href*="grnh.se"]',
    '.postings-btn',
    '#grnhse_app a',
    'a[data-job-id]',
    '.job-application-button',
    '.application-button',
    # General patterns
    'a[href*="apply"]',
    'a[href*="Apply"]',
    'button[data-qa="apply-button"]',
    'a[data-qa="apply-button"]',
    'button[class*="apply"]',
    'button[class*="Apply"]',
    'a[class*="apply"]',
    'a[class*="Apply"]',
    '[data-testid="apply-button"]',
    '[data-testid*="apply"]',
    '.apply-button',
    '.Apply-button',
    '#apply-button',
    '#apply',
]

APPLY_BUTTON_TEXT_PATTERNS = [
    "Apply Now",
    "Apply now",
    "apply now",
    "Apply",
    "apply",
    "APPLY NOW",
    "APPLY",
    "Apply for this job",
    "Apply to this job",
    "Apply for Job",
    "Submit Application",
    "Start Application",
    "Apply for this position",
    "Apply for position",
]


async def find_and_click_apply_button(page: Page) -> bool:
    """
    Find and click an Apply button on a job description page.
    Returns True if a button was found and clicked, False otherwise.
    """
    print("  Looking for Apply button...")

    # Method 1: Try selector-based matching first
    for selector in APPLY_BUTTON_SELECTORS:
        try:
            element = await page.query_selector(selector)
            if element and await element.is_visible():
                text = await element.inner_text()
                print(f"  Found via selector '{selector}': {text[:30] if text else 'no text'}")
                await element.click()
                await asyncio.sleep(2)  # Wait for page/modal to load
                return True
        except Exception:
            continue

    # Method 2: Try text-based matching with Playwright's text selector
    for text_pattern in APPLY_BUTTON_TEXT_PATTERNS:
        try:
            # Use Playwright's text selector (case-insensitive with 'i' flag)
            button = await page.query_selector(f'button:has-text("{text_pattern}")')
            if button and await button.is_visible():
                print(f"  Found button with text: {text_pattern}")
                await button.click()
                await asyncio.sleep(2)
                return True

            link = await page.query_selector(f'a:has-text("{text_pattern}")')
            if link and await link.is_visible():
                print(f"  Found link with text: {text_pattern}")
                await link.click()
                await asyncio.sleep(2)
                return True
        except Exception:
            continue

    # Method 3: Scan all clickable elements for Apply text
    try:
        # Get all potential clickable elements
        elements = await page.query_selector_all(
            'button, a, [role="button"], input[type="submit"], input[type="button"], '
            'div[onclick], span[onclick], [class*="btn"], [class*="button"]'
        )
        print(f"  Scanning {len(elements)} clickable elements...")

        for element in elements:
            try:
                text = await element.inner_text()
                if not text:
                    continue
                text_clean = text.strip().lower()

                # Check if contains "apply"
                if "apply" in text_clean and len(text_clean) < 50:  # Avoid long text blocks
                    if await element.is_visible():
                        print(f"  Found element with 'apply': '{text.strip()[:30]}'")
                        await element.click()
                        await asyncio.sleep(2)
                        return True
            except Exception:
                continue
    except Exception as e:
        print(f"  Error scanning elements: {e}")

    # Method 4: Try using page.get_by_role for better accessibility matching
    try:
        apply_button = page.get_by_role("button", name="Apply Now")
        if await apply_button.count() > 0:
            print("  Found via get_by_role: Apply Now button")
            await apply_button.first.click()
            await asyncio.sleep(2)
            return True

        apply_link = page.get_by_role("link", name="Apply Now")
        if await apply_link.count() > 0:
            print("  Found via get_by_role: Apply Now link")
            await apply_link.first.click()
            await asyncio.sleep(2)
            return True

        apply_button2 = page.get_by_role("button", name="Apply")
        if await apply_button2.count() > 0:
            print("  Found via get_by_role: Apply button")
            await apply_button2.first.click()
            await asyncio.sleep(2)
            return True

        apply_link2 = page.get_by_role("link", name="Apply")
        if await apply_link2.count() > 0:
            print("  Found via get_by_role: Apply link")
            await apply_link2.first.click()
            await asyncio.sleep(2)
            return True
    except Exception as e:
        print(f"  get_by_role error: {e}")

    print("  No Apply button found")
    return False


# Common "Submit" button selectors and text patterns
SUBMIT_BUTTON_SELECTORS = [
    # Greenhouse specific
    'button[type="submit"]',
    'input[type="submit"]',
    '#submit_app',
    '#submit-app',
    '.submit-button',
    '[data-qa="submit-button"]',
    # General patterns
    'button[class*="submit"]',
    'button[class*="Submit"]',
    '[data-testid="submit-button"]',
    '[data-testid*="submit"]',
]

SUBMIT_BUTTON_TEXT_PATTERNS = [
    "Submit Application",
    "Submit application",
    "submit application",
    "Submit",
    "submit",
    "SUBMIT",
    "Apply",
    "Send Application",
    "Complete Application",
]


async def _search_submit_in_frame(frame) -> bool:
    """
    Search for and click submit button within a given frame/page.
    Returns True if found and clicked, False otherwise.
    """
    # Method 1: Try selector-based matching first
    for selector in SUBMIT_BUTTON_SELECTORS:
        try:
            element = await frame.query_selector(selector)
            if element and await element.is_visible():
                text = await element.inner_text()
                print(f"  Found via selector '{selector}': {text[:30] if text else 'no text'}")
                await element.click()
                await asyncio.sleep(2)
                return True
        except Exception:
            continue

    # Method 2: Try text-based matching
    for text_pattern in SUBMIT_BUTTON_TEXT_PATTERNS:
        try:
            button = await frame.query_selector(f'button:has-text("{text_pattern}")')
            if button and await button.is_visible():
                print(f"  Found button with text: {text_pattern}")
                await button.click()
                await asyncio.sleep(2)
                return True

            # Also check input elements
            input_btn = await frame.query_selector(f'input[value*="{text_pattern}"]')
            if input_btn and await input_btn.is_visible():
                print(f"  Found input with value: {text_pattern}")
                await input_btn.click()
                await asyncio.sleep(2)
                return True
        except Exception:
            continue

    # Method 3: Use get_by_role for accessibility matching
    try:
        submit_button = frame.get_by_role("button", name="Submit Application")
        if await submit_button.count() > 0:
            print("  Found via get_by_role: Submit Application")
            await submit_button.first.click()
            await asyncio.sleep(2)
            return True

        submit_button2 = frame.get_by_role("button", name="Submit")
        if await submit_button2.count() > 0:
            print("  Found via get_by_role: Submit")
            await submit_button2.first.click()
            await asyncio.sleep(2)
            return True
    except Exception as e:
        print(f"  get_by_role error: {e}")

    return False


async def find_and_click_submit_button(page: Page) -> bool:
    """
    Find and click a Submit button on the application form.
    Handles both main page and iframe-embedded forms (e.g., Greenhouse).
    Returns True if a button was found and clicked, False otherwise.
    """
    print("  Looking for Submit button...")

    # First, check for Greenhouse iframe (form may be embedded)
    iframe_selectors = [
        '#grnhse_iframe',
        'iframe[src*="greenhouse"]',
        'iframe[src*="boards.greenhouse.io"]',
    ]

    for selector in iframe_selectors:
        try:
            iframe_element = await page.query_selector(selector)
            if iframe_element:
                print(f"  Found iframe: {selector}")
                iframe = await iframe_element.content_frame()
                if iframe:
                    print("  Searching for submit button inside iframe...")
                    if await _search_submit_in_frame(iframe):
                        return True
        except Exception as e:
            print(f"  Iframe error: {e}")
            continue

    # Fall back to searching main page
    print("  Searching for submit button on main page...")
    if await _search_submit_in_frame(page):
        return True

    print("  No Submit button found")
    return False


async def wait_for_url_change(
    page: Page,
    initial_url: str,
    timeout_seconds: int = 300,
    check_interval: int = 2,
) -> bool:
    """
    Wait for URL to change (indicating user clicked Submit).

    Args:
        page: Playwright page object
        initial_url: The URL before submission
        timeout_seconds: Maximum time to wait (default: 5 minutes)
        check_interval: How often to check URL (default: 2 seconds)

    Returns:
        True if URL changed, False if timeout
    """
    elapsed = 0
    console.print("[dim]Waiting for you to click Submit in Chrome...[/dim]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Watching for submission...", total=None)

        while elapsed < timeout_seconds:
            current_url = page.url
            if current_url != initial_url:
                progress.update(task, description="[green]✓ Submission detected![/green]")
                console.print(f"[green]✓[/green] Detected submission (URL changed)")
                return True

            await asyncio.sleep(check_interval)
            elapsed += check_interval

            # Update progress message every 30 seconds
            if elapsed % 30 == 0:
                minutes_left = (timeout_seconds - elapsed) // 60
                progress.update(task, description=f"Waiting... ({minutes_left}m remaining)")

    console.print("[yellow]⚠[/yellow] Timeout waiting for submission")
    return False


async def process_job(
    browser: BrowserManager,
    profile: Profile,
    profile_name: str,
    llm: LLMHelper,
    logger: ApplicationLogger,
    job: dict,
    auto_submit: bool = False,
    browser_confirm_only: bool = False,
) -> bool:
    """
    Process a single job application.

    Args:
        browser_confirm_only: If True, skip terminal confirmation and wait for
                             user to submit in browser (detected via URL change)

    Returns True if successful, False otherwise.
    """
    job_url = job.get("url", "")
    job_title = job.get("title", "")
    company_name = job.get("company", "")

    if not job_url:
        console.print("[red]No URL provided for job[/red]")
        return False

    logger.start_application(job_url, job_title, company_name)
    ui = ConfirmationUI()

    try:
        # Navigate to job page
        ui.display_info(f"Navigating to {company_name} - {job_title}")

        if not await browser.navigate(job_url):
            logger.log_error("Failed to navigate to job URL")
            logger.complete_application(success=False)
            return False

        logger.update_status(ApplicationStatus.NAVIGATED)

        # Capture initial screenshot
        await logger.capture_screenshot(browser.page, "initial")

        # Detect ATS
        page_content = await browser.get_page_content()
        current_url = await browser.get_current_url()
        ats_result = detect_ats(current_url, page_content)

        console.print(f"[dim]ATS detected: {ats_result.ats_type.value} "
                     f"(confidence: {ats_result.confidence:.0%})[/dim]")

        logger.log_event("ATS detected", {
            "type": ats_result.ats_type.value,
            "confidence": ats_result.confidence,
        })

        # First check if form already exists on the page (some pages have embedded forms)
        console.print("[dim]Checking for existing form...[/dim]")
        job_info = f"{company_name} - {job_title}"
        filler = FormFiller(
            browser.page,
            profile,
            profile_name=profile_name,
            job_info=job_info,
            llm_helper=llm,
        )
        fields = await filler.extract_form_fields()

        # If form found, skip Apply button click
        if len(fields) > 3:
            console.print(f"[dim]Found {len(fields)} form fields on page (no Apply click needed)[/dim]")
        else:
            # Try to click Apply button
            console.print("[dim]Looking for Apply button...[/dim]")
            if await find_and_click_apply_button(browser.page):
                console.print("[green]✓[/green] Clicked Apply button")
                logger.log_event("Clicked Apply button")

                # Wait for page navigation/modal and iframe to load
                await asyncio.sleep(3)

                # Re-capture page info after clicking
                await logger.capture_screenshot(browser.page, "after_apply_click")

                # Check if URL changed (navigated to application form)
                new_url = await browser.get_current_url()
                if new_url != current_url:
                    console.print(f"[dim]Navigated to: {new_url}[/dim]")
                    logger.log_event("Navigated to application form", {"new_url": new_url})

                    # Re-detect ATS on new page
                    page_content = await browser.get_page_content()
                    ats_result = detect_ats(new_url, page_content)
                    console.print(f"[dim]ATS detected: {ats_result.ats_type.value} "
                                 f"(confidence: {ats_result.confidence:.0%})[/dim]")

                # Wait for iframe content to fully load
                await asyncio.sleep(3)

                # Check for Greenhouse iframe that might have loaded dynamically
                grnhse_iframe = await browser.page.query_selector('#grnhse_iframe, iframe[src*="greenhouse"]')
                if grnhse_iframe:
                    console.print("[dim]Found Greenhouse iframe, waiting for it to load...[/dim]")
                    await asyncio.sleep(3)
            else:
                console.print("[dim]No Apply button found, checking for form...[/dim]")

            # Re-extract form fields after clicking Apply
            console.print("[dim]Analyzing form fields...[/dim]")
            fields = await filler.extract_form_fields()
            console.print(f"[dim]Found {len(fields)} form fields[/dim]")

        # If no fields found, wait and retry (form might be loading)
        if not fields or len(fields) < 3:
            console.print("[dim]Few/no fields found, waiting for form to load...[/dim]")
            await asyncio.sleep(5)  # Longer wait for slow-loading forms

            # Check for Greenhouse iframe again
            grnhse_iframe = await browser.page.query_selector('#grnhse_iframe, iframe[src*="greenhouse"]')
            if grnhse_iframe:
                console.print("[dim]Found Greenhouse iframe, waiting for content...[/dim]")
                await asyncio.sleep(3)

            fields = await filler.extract_form_fields()
            console.print(f"[dim]Retry: Found {len(fields)} form fields[/dim]")

        # Still no fields - try scrolling down and looking for form
        if not fields:
            console.print("[dim]Scrolling to find form...[/dim]")
            await browser.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
            fields = await filler.extract_form_fields()
            console.print(f"[dim]After scroll: Found {len(fields)} form fields[/dim]")

        if not fields:
            ui.display_warning("No form fields detected. The page may require manual interaction.")
            logger.skip_application("No form fields detected")
            return False

        logger.update_status(ApplicationStatus.FORM_DETECTED)
        console.print(f"[dim]Found {len(fields)} form fields[/dim]")

        # Fill form fields
        console.print("[dim]Filling form fields...[/dim]")
        filled_fields = await filler.fill_all_fields(fields)

        logger.update_status(ApplicationStatus.FILLED)

        # Log filled fields
        logger.log_filled_fields([
            {
                "label": f.field.label,
                "value": f.filled_value,
                "success": f.success,
                "high_risk": f.is_high_risk,
            }
            for f in filled_fields
        ])

        # Capture screenshot after filling
        await logger.capture_screenshot(browser.page, "after_fill")

        # Handle unknown/custom fields with LLM
        unknown_required = [
            f for f in filled_fields
            if not f.success and f.field.is_required
        ]

        if unknown_required and llm.is_available():
            console.print(f"[dim]Using LLM for {len(unknown_required)} unknown fields...[/dim]")

            for field_result in unknown_required:
                suggestion = llm.suggest_value(
                    field_result.field,
                    job_title=job_title,
                    company_name=company_name,
                )
                if suggestion:
                    # Try to fill with LLM suggestion
                    result = await filler.fill_field(field_result.field)
                    if result.success:
                        # Update the field result
                        field_result.filled_value = result.filled_value
                        field_result.success = True

        # Human confirmation
        if not auto_submit:
            if browser_confirm_only:
                # New mode: Show summary and wait for browser submission
                ui.display_summary(filled_fields, job_title, company_name)
                console.print()
                console.print(Panel(
                    f"[bold green]✓ Form filled successfully![/bold green]\n\n"
                    f"[bold]Next steps:[/bold]\n"
                    f"1. Switch to Chrome window\n"
                    f"2. Review the filled form\n"
                    f"3. Click the [bold cyan]Submit[/bold cyan] button\n\n"
                    f"[dim]The script will automatically detect your submission and move to the next job.[/dim]",
                    style="blue",
                    title=f"{company_name} - {job_title}",
                ))

                # Capture URL before waiting
                current_url = await browser.get_current_url()
                await logger.capture_screenshot(browser.page, "pre_submit")

                # Wait for URL to change (user clicked Submit)
                submitted = await wait_for_url_change(browser.page, current_url)

                if submitted:
                    await asyncio.sleep(2)  # Wait for submission to process
                    await logger.capture_screenshot(browser.page, "after_submit")
                    logger.update_status(ApplicationStatus.SUBMITTED)
                    console.print(f"[green]✓[/green] Application submitted for {company_name} - {job_title}")
                else:
                    console.print(f"[yellow]⚠[/yellow] Timeout: Assuming application was submitted")
                    logger.update_status(ApplicationStatus.SUBMITTED)

            else:
                # Old mode: Terminal confirmation
                confirmed = review_and_confirm(filled_fields, job_title, company_name)

                if not confirmed:
                    ui.display_info("Application cancelled by user")
                    logger.skip_application("User cancelled")
                    return False

                logger.update_status(ApplicationStatus.CONFIRMED)

                # Capture pre-submit screenshot
                await logger.capture_screenshot(browser.page, "pre_submit")

                # Human review mode: let human click submit manually
                ui.display_success(
                    f"Form filled for {company_name} - {job_title}\n"
                    "Review the browser and submit manually when ready."
                )
        else:
            # Auto-pilot mode: auto-click submit button
            logger.update_status(ApplicationStatus.CONFIRMED)
            await logger.capture_screenshot(browser.page, "pre_submit")

            console.print("[dim]Auto-submit enabled. Looking for submit button...[/dim]")
            submitted = await find_and_click_submit_button(browser.page)
            if submitted:
                await asyncio.sleep(2)  # Wait for submission to process
                await logger.capture_screenshot(browser.page, "after_submit")
                ui.display_success(
                    f"Form submitted for {company_name} - {job_title}"
                )
                logger.update_status(ApplicationStatus.SUBMITTED)
            else:
                ui.display_warning(
                    f"Form filled for {company_name} - {job_title}\n"
                    "Could not find submit button. Please submit manually."
                )

        logger.complete_application(success=True)
        return True

    except Exception as e:
        console.print(f"[red]Error processing job: {e}[/red]")
        logger.log_error(str(e))
        logger.complete_application(success=False)
        return False


async def main(
    jobs_file: Optional[str] = None,
    profile_name: Optional[str] = None,
    profile_path: Optional[str] = None,
    cdp_url: str = "http://localhost:9222",
    auto_submit: bool = False,
):
    """Main entry point."""
    # Load profile
    try:
        profile = load_profile(profile_name=profile_name, config_path=profile_path)
        display_name = profile_name or (profile_path if profile_path else "default")
        console.print(f"[green]✓[/green] Profile loaded: [bold]{display_name}[/bold]")
    except FileNotFoundError as e:
        console.print(f"[red]Error loading profile:[/red] {e}")
        profiles = get_available_profiles()
        if profiles:
            console.print("\n[bold]Available profiles:[/bold]")
            for p in profiles:
                console.print(f"  - {p}")
        return 1

    # Initialize LLM helper
    llm = LLMHelper(profile)
    if llm.is_available():
        console.print("[green]✓[/green] LLM helper available")
    else:
        console.print("[yellow]⚠[/yellow] LLM helper not available (set ANTHROPIC_API_KEY)")

    # Load jobs
    jobs = []
    if jobs_file:
        jobs_path = Path(jobs_file)
        if not jobs_path.exists():
            console.print(f"[red]Jobs file not found:[/red] {jobs_file}")
            return 1

        with open(jobs_path) as f:
            jobs = json.load(f)

        console.print(f"[green]✓[/green] Loaded {len(jobs)} jobs")
    else:
        # Interactive mode - process current page
        console.print("[yellow]No jobs file provided. Running in interactive mode.[/yellow]")
        jobs = [{"url": "", "title": "", "company": ""}]

    # Initialize logger
    logger = ApplicationLogger()
    console.print(f"[green]✓[/green] Logging to {logger.session_dir}")

    # Connect to browser
    console.print(f"[dim]Connecting to Chrome at {cdp_url}...[/dim]")

    try:
        async with BrowserManager(cdp_url) as browser:
            console.print("[green]✓[/green] Connected to Chrome")

            for i, job in enumerate(jobs):
                if jobs_file:
                    console.print(f"\n[bold]Processing job {i+1}/{len(jobs)}[/bold]")

                if not job.get("url"):
                    # Interactive mode - use current page
                    current_url = await browser.get_current_url()
                    if current_url and current_url != "about:blank":
                        job["url"] = current_url
                        console.print(f"Using current page: {current_url}")
                    else:
                        console.print("[red]No URL available. Navigate to a job page first.[/red]")
                        continue

                success = await process_job(
                    browser=browser,
                    profile=profile,
                    profile_name=display_name,
                    llm=llm,
                    logger=logger,
                    job=job,
                    auto_submit=auto_submit,
                )

                if not success:
                    console.print(f"[yellow]Failed to process job: {job.get('company', 'Unknown')}[/yellow]")

                # Small delay between jobs
                if i < len(jobs) - 1:
                    await asyncio.sleep(2)

            # Print final report
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
        description="Hermes - Job Application Automation Agent"
    )
    parser.add_argument(
        "--jobs", "-j",
        help="Path to JSON file with job listings",
        dest="jobs_file",
    )
    parser.add_argument(
        "--profile", "-p",
        help="Profile name (e.g., 'default', 'Ming'). Profiles are stored in config/profiles/",
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
        help="Fully automated mode: auto-click submit button after filling form. "
             "Without this flag, form is filled but human must click submit manually.",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available profiles and exit",
    )

    args = parser.parse_args()

    # Handle --list-profiles
    if args.list_profiles:
        profiles = get_available_profiles()
        if profiles:
            console.print("[bold]Available profiles:[/bold]")
            for p in profiles:
                console.print(f"  - {p}")
        else:
            console.print("[yellow]No profiles found. Create one in config/profiles/<name>/profile.yaml[/yellow]")
        return 0

    return asyncio.run(main(
        jobs_file=args.jobs_file,
        profile_name=args.profile_name,
        profile_path=args.profile_path,
        cdp_url=args.cdp_url,
        auto_submit=args.auto_pilot,
    ))


if __name__ == "__main__":
    sys.exit(cli())
