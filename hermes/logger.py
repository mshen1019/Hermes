"""
Application logging and screenshot capture module.
"""

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.async_api import Page


class ApplicationStatus(Enum):
    """Status of a job application."""
    PENDING = "pending"
    NAVIGATED = "navigated"
    FORM_DETECTED = "form_detected"
    FILLED = "filled"
    CONFIRMED = "confirmed"
    SUBMITTED = "submitted"
    FAILED = "failed"
    SKIPPED = "skipped"


class ApplicationLogger:
    """Logs application attempts and captures screenshots."""

    MAX_LOG_FOLDERS = 10  # Keep only the last N log sessions

    def __init__(self, logs_dir: Optional[str] = None):
        if logs_dir:
            self.logs_dir = Path(logs_dir)
        else:
            self.logs_dir = Path(__file__).parent.parent / "logs"

        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Clean up old log folders before creating new one
        self._cleanup_old_logs()

        # Create session log file
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.logs_dir / self.session_id
        self.session_dir.mkdir(exist_ok=True)

        self.log_file = self.session_dir / "session.json"
        self.applications: List[Dict[str, Any]] = []

        self._current_app: Optional[Dict[str, Any]] = None

    def _cleanup_old_logs(self):
        """Remove old log folders, keeping only the most recent ones."""
        import shutil

        try:
            # Get all session directories (format: YYYYMMDD_HHMMSS)
            log_dirs = sorted([
                d for d in self.logs_dir.iterdir()
                if d.is_dir() and d.name[0].isdigit()
            ])

            # Remove oldest directories if we have more than MAX_LOG_FOLDERS
            while len(log_dirs) >= self.MAX_LOG_FOLDERS:
                oldest = log_dirs.pop(0)
                shutil.rmtree(oldest)
        except Exception:
            pass  # Don't fail if cleanup fails

    def start_application(
        self,
        job_url: str,
        job_title: str = "",
        company_name: str = "",
    ):
        """Start logging a new application attempt."""
        self._current_app = {
            "job_url": job_url,
            "job_title": job_title,
            "company_name": company_name,
            "status": ApplicationStatus.PENDING.value,
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "events": [],
            "screenshots": [],
            "filled_fields": [],
            "error": None,
        }

    def log_event(self, event: str, details: Optional[Dict[str, Any]] = None):
        """Log an event during the application process."""
        if not self._current_app:
            return

        self._current_app["events"].append({
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "details": details or {},
        })

    def update_status(self, status: ApplicationStatus):
        """Update the current application status."""
        if not self._current_app:
            return

        self._current_app["status"] = status.value
        self.log_event(f"Status changed to {status.value}")

    def log_filled_fields(self, fields: List[Dict[str, Any]]):
        """Log the fields that were filled."""
        if not self._current_app:
            return

        self._current_app["filled_fields"] = fields

    async def capture_screenshot(
        self,
        page: Page,
        name: str,
        full_page: bool = True,
    ) -> Optional[str]:
        """Capture a screenshot and log it."""
        if not self._current_app:
            return None

        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"{timestamp}_{name}.png"
        filepath = self.session_dir / filename

        try:
            await page.screenshot(path=str(filepath), full_page=full_page)

            self._current_app["screenshots"].append({
                "name": name,
                "path": str(filepath),
                "timestamp": datetime.now().isoformat(),
            })

            return str(filepath)
        except Exception as e:
            self.log_event(f"Screenshot failed: {e}")
            return None

    def log_error(self, error: str):
        """Log an error for the current application."""
        if not self._current_app:
            return

        self._current_app["error"] = error
        self.log_event(f"Error: {error}")

    def complete_application(self, success: bool = True):
        """Mark the current application as complete and save to log."""
        if not self._current_app:
            return

        self._current_app["completed_at"] = datetime.now().isoformat()

        if success and self._current_app["status"] == ApplicationStatus.CONFIRMED.value:
            self._current_app["status"] = ApplicationStatus.SUBMITTED.value
        elif not success and self._current_app["status"] not in (
            ApplicationStatus.SKIPPED.value,
            ApplicationStatus.FAILED.value,
        ):
            self._current_app["status"] = ApplicationStatus.FAILED.value

        self.applications.append(self._current_app)
        self._current_app = None

        # Save to file
        self._save_log()

    def skip_application(self, reason: str):
        """Mark the current application as skipped."""
        if not self._current_app:
            return

        self._current_app["status"] = ApplicationStatus.SKIPPED.value
        self.log_event(f"Skipped: {reason}")
        self.complete_application(success=False)

    def _save_log(self):
        """Save the log to file."""
        log_data = {
            "session_id": self.session_id,
            "started_at": self.applications[0]["started_at"] if self.applications else None,
            "applications": self.applications,
            "summary": self._get_summary(),
        }

        with open(self.log_file, "w") as f:
            json.dump(log_data, f, indent=2)

    def _get_summary(self) -> Dict[str, int]:
        """Get summary statistics."""
        summary = {status.value: 0 for status in ApplicationStatus}

        for app in self.applications:
            status = app.get("status", ApplicationStatus.PENDING.value)
            if status in summary:
                summary[status] += 1

        return summary

    def get_session_report(self) -> str:
        """Generate a human-readable session report."""
        summary = self._get_summary()

        report = f"""
=== Application Session Report ===
Session ID: {self.session_id}
Log Directory: {self.session_dir}

Summary:
  - Submitted: {summary['submitted']}
  - Failed: {summary['failed']}
  - Skipped: {summary['skipped']}
  - Total: {len(self.applications)}

Details:
"""
        for app in self.applications:
            status_icon = {
                "submitted": "✓",
                "failed": "✗",
                "skipped": "⊘",
            }.get(app["status"], "?")

            report += f"""
  {status_icon} {app.get('company_name', 'Unknown')} - {app.get('job_title', 'Unknown')}
    URL: {app['job_url']}
    Status: {app['status']}
"""
            if app.get("error"):
                report += f"    Error: {app['error']}\n"

        return report
