import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from agents import Agent, Runner, function_tool
from openpyxl import load_workbook
from pydantic import BaseModel, Field

from production.audit import AuditLog
from production.models import InvestigationRequest
from production.service import InvestigationService
from production.spreadsheet_provider import SpreadsheetEvidenceProvider


DATA_DIR = Path(__file__).parent
LOCAL_PROVIDER = SpreadsheetEvidenceProvider(DATA_DIR)
LOCAL_SERVICE = InvestigationService(
    provider=LOCAL_PROVIDER,
    audit_log=AuditLog(DATA_DIR / "local_data" / "audit.jsonl"),
)


class RebateInvestigationResult(BaseModel):
    """The predictable final answer returned by the agent."""

    customer: str | None = Field(
        description="Customer being investigated, or null if the user did not provide one."
    )
    quarter: str | None = Field(
        description="Quarter being investigated, such as 2026-Q2, or null if missing."
    )
    status: Literal[
        "completed", "needs_information", "not_found", "review_required"
    ] = Field(description="Outcome category for the investigation.")
    eligible_sales: float | None = Field(
        description="Rebate-eligible sales for the quarter, or null if not established."
    )
    quarterly_minimum: float | None = Field(
        description="Minimum eligible sales required by the agreement, or null if unknown."
    )
    rebate_rate: float | None = Field(
        description="Agreement rebate rate as a decimal, or null if unknown."
    )
    expected_rebate: float | None = Field(
        description="Calculated rebate expected for the quarter, or null if unknown."
    )
    amount_paid: float | None = Field(
        description="Total rebate payments found, or null if payment data was not checked."
    )
    variance: float | None = Field(
        description=(
            "Expected rebate minus amount paid. A positive value may still be owed. "
            "Null if it cannot be calculated."
        )
    )
    conclusion: str = Field(description="Concise explanation of the investigation result.")
    next_action: str = Field(description="Recommended next step for a human reviewer.")


def show_tool_activity(tool_name: str, **details: str) -> None:
    """Print a visible, local activity message when the agent runs a tool."""
    arguments = ", ".join(f"{key}={value}" for key, value in details.items())
    print(f"\n[Tool activity] Running {tool_name}({arguments})")


def _json_value(value: Any) -> Any:
    """Convert spreadsheet values into JSON-safe values."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _read_rows(filename: str) -> list[dict[str, Any]]:
    """Read one spreadsheet and return its rows as dictionaries."""
    workbook = load_workbook(DATA_DIR / filename, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    headers = [str(value) for value in next(rows)]
    records = [
        {header: _json_value(value) for header, value in zip(headers, row)}
        for row in rows
    ]
    workbook.close()
    return records


def _matches(value: Any, requested: str) -> bool:
    """Compare spreadsheet text without caring about capitalization or spaces."""
    return str(value).strip().casefold() == requested.strip().casefold()


def _get_rebate_agreement(customer: str) -> str:
    matches = [
        row
        for row in _read_rows("rebate_agreements.xlsx")
        if _matches(row["Customer"], customer)
    ]
    return json.dumps({"customer": customer, "records": matches}, separators=(",", ":"))


@function_tool
def get_rebate_agreement(customer: str) -> str:
    """Get the rebate agreement for one customer."""
    show_tool_activity("get_rebate_agreement", customer=customer)
    return _get_rebate_agreement(customer)


def _get_transactions(customer: str, quarter: str) -> str:
    matches = [
        row
        for row in _read_rows("transactions.xlsx")
        if _matches(row["Customer"], customer) and _matches(row["Quarter"], quarter)
    ]
    total_sales = sum(float(row["Net Sales"] or 0) for row in matches)
    agreements = json.loads(_get_rebate_agreement(customer))["records"]
    eligible_codes = {
        code
        for agreement in agreements
        if _matches(agreement["Status"], "Active")
        for code in str(agreement["Eligible Product Codes"] or "").split(";")
    }
    eligible_sales = sum(
        float(row["Net Sales"] or 0)
        for row in matches
        if _matches(row["Record Status"], "Posted")
        and str(row["Product Code"]) in eligible_codes
        and not _matches(row["Eligibility Override"], "No")
    )
    result = {
        "customer": customer,
        "quarter": quarter,
        "transaction_count": len(matches),
        "total_sales": total_sales,
        "eligible_sales": eligible_sales,
        "records": matches,
    }
    return json.dumps(result, separators=(",", ":"))


@function_tool
def get_transactions(customer: str, quarter: str) -> str:
    """Get sales transactions for one customer and quarter, such as 2026-Q2."""
    show_tool_activity("get_transactions", customer=customer, quarter=quarter)
    return _get_transactions(customer, quarter)


def _get_rebate_payments(customer: str, quarter: str) -> str:
    matches = [
        row
        for row in _read_rows("rebate_payments.xlsx")
        if _matches(row["Customer"], customer) and _matches(row["Quarter"], quarter)
    ]
    total_paid = sum(
        float(row["Payment Amount"] or 0)
        for row in matches
        if _matches(row["Payment Status"], "Paid")
        and _matches(row["Approval Status"], "Approved")
    )
    result = {
        "customer": customer,
        "quarter": quarter,
        "payment_count": len(matches),
        "total_paid": total_paid,
        "records": matches,
    }
    return json.dumps(result, separators=(",", ":"))


@function_tool
def get_rebate_payments(customer: str, quarter: str) -> str:
    """Get rebate payment records for one customer and quarter, such as 2026-Q2."""
    show_tool_activity("get_rebate_payments", customer=customer, quarter=quarter)
    return _get_rebate_payments(customer, quarter)


def _run_deterministic_investigation(customer: str, quarter: str) -> str:
    """Run permission checks, spreadsheet retrieval, and exact financial rules."""
    tenant_id = LOCAL_PROVIDER.tenant_for_customer(customer)
    request = InvestigationRequest(
        request_id=f"LOCAL-{uuid4()}",
        tenant_id=tenant_id,
        actor_id="local-laptop-user",
        actor_roles={"investigator"},
        customer=customer,
        quarter=quarter,
    )
    return LOCAL_SERVICE.investigate(request).model_dump_json()


@function_tool
def calculate_rebate_deterministically(customer: str, quarter: str) -> str:
    """Calculate and reconcile a quarterly rebate using controlled financial rules. Always use this tool for rebate arithmetic."""
    show_tool_activity(
        "calculate_rebate_deterministically", customer=customer, quarter=quarter
    )
    return _run_deterministic_investigation(customer, quarter)


rebate_agent = Agent(
    name="Rebate Investigation Agent",
    model="gpt-5.6-luna",
    instructions=(
        "Investigate rebate questions using the available tools when needed. "
        "For every question that needs eligibility, threshold, expected rebate, paid amount, or variance, "
        "you MUST call calculate_rebate_deterministically and copy its financial fields exactly. "
        "Never perform or override financial arithmetic yourself. "
        "Choose only the tools required for the question. For an end-to-end rebate "
        "investigation, compare the customer's agreement, eligible transactions, "
        "and payments for the requested quarter. If the customer or quarter is "
        "missing, return needs_information and explain what is needed before calling "
        "a tool. The deterministic tool owns the eligibility, threshold, rate, "
        "rounding, expected rebate, payment, and variance rules. Use null for any number "
        "that was not established; do not replace missing facts with zero. Give a "
        "concise conclusion and next action. Do not invent missing facts."
    ),
    tools=[
        get_rebate_agreement,
        get_transactions,
        get_rebate_payments,
        calculate_rebate_deterministically,
    ],
    output_type=RebateInvestigationResult,
)


def main() -> None:
    question = input("Describe the rebate issue you want to investigate:\n> ")
    result = Runner.run_sync(rebate_agent, question)
    print("\nAgent response:\n")
    print(result.final_output.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
