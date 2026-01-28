"""
Human confirmation interface for reviewing filled fields before submission.
"""

from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from .field_mapping import is_high_risk_field
from .form_filler import FilledField


class ConfirmationUI:
    """CLI interface for human confirmation of filled fields."""

    def __init__(self):
        self.console = Console()

    def display_summary(
        self,
        filled_fields: List[FilledField],
        job_title: str = "",
        company_name: str = "",
    ):
        """Display a summary of all filled fields."""
        self.console.print()
        self.console.print(
            Panel(
                f"[bold]Job Application Summary[/bold]\n"
                f"Position: {job_title or 'Unknown'}\n"
                f"Company: {company_name or 'Unknown'}",
                style="blue",
            )
        )

        # Create table for filled fields
        table = Table(title="Filled Fields", show_header=True)
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Status", justify="center")
        table.add_column("Risk", justify="center")

        # Separate high-risk and normal fields
        high_risk_fields = []
        normal_fields = []

        for f in filled_fields:
            if f.is_high_risk:
                high_risk_fields.append(f)
            else:
                normal_fields.append(f)

        # Add normal fields first
        for f in normal_fields:
            status = "[green]✓[/green]" if f.success else "[red]✗[/red]"
            value = f.filled_value[:50] + "..." if len(f.filled_value) > 50 else f.filled_value
            table.add_row(
                f.field.label,
                value,
                status,
                "",
            )

        self.console.print(table)

        # Display high-risk fields separately with warning
        if high_risk_fields:
            self.console.print()
            self.console.print(
                Panel(
                    "[bold yellow]⚠️  HIGH-RISK FIELDS[/bold yellow]\n"
                    "The following fields may have legal or career implications. "
                    "Please review carefully.",
                    style="yellow",
                )
            )

            risk_table = Table(show_header=True, style="yellow")
            risk_table.add_column("Field", style="yellow")
            risk_table.add_column("Value", style="bold yellow")
            risk_table.add_column("Status", justify="center")

            for f in high_risk_fields:
                status = "[green]✓[/green]" if f.success else "[red]✗[/red]"
                risk_table.add_row(
                    f.field.label,
                    f.filled_value,
                    status,
                )

            self.console.print(risk_table)

        # Show unfilled required fields
        unfilled = [f for f in filled_fields if not f.success and f.field.is_required]
        if unfilled:
            self.console.print()
            self.console.print(
                Panel(
                    "[bold red]❌ UNFILLED REQUIRED FIELDS[/bold red]\n"
                    "The following required fields could not be filled:",
                    style="red",
                )
            )
            for f in unfilled:
                self.console.print(f"  • {f.field.label}")

    def confirm_submission(self) -> bool:
        """Prompt user to confirm submission."""
        self.console.print()
        return Confirm.ask(
            "[bold]Do you want to proceed with submission?[/bold]",
            default=False,
        )

    def confirm_field(self, field: FilledField) -> bool:
        """Prompt user to confirm a specific field value."""
        self.console.print()
        self.console.print(
            Panel(
                f"[bold]Field:[/bold] {field.field.label}\n"
                f"[bold]Value:[/bold] {field.filled_value}",
                style="cyan",
            )
        )
        return Confirm.ask("Is this value correct?", default=True)

    def request_correction(self, field: FilledField) -> str:
        """Request a corrected value from the user."""
        self.console.print()
        self.console.print(f"Current value for [bold]{field.field.label}[/bold]: {field.filled_value}")
        corrected = self.console.input("[bold]Enter corrected value:[/bold] ")
        return corrected.strip()

    def display_error(self, message: str):
        """Display an error message."""
        self.console.print()
        self.console.print(Panel(f"[bold red]Error:[/bold red] {message}", style="red"))

    def display_success(self, message: str):
        """Display a success message."""
        self.console.print()
        self.console.print(Panel(f"[bold green]✓[/bold green] {message}", style="green"))

    def display_info(self, message: str):
        """Display an info message."""
        self.console.print()
        self.console.print(Panel(message, style="blue"))

    def display_warning(self, message: str):
        """Display a warning message."""
        self.console.print()
        self.console.print(Panel(f"[bold yellow]⚠️[/bold yellow] {message}", style="yellow"))


def review_and_confirm(
    filled_fields: List[FilledField],
    job_title: str = "",
    company_name: str = "",
) -> bool:
    """
    Main function to review filled fields and get user confirmation.

    Returns True if user confirms, False otherwise.
    """
    ui = ConfirmationUI()
    ui.display_summary(filled_fields, job_title, company_name)
    return ui.confirm_submission()
