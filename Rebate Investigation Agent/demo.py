"""Free, no-API demonstration of the local rebate calculation service."""

import argparse
import sys
from pathlib import Path
from uuid import uuid4

from production.audit import AuditLog
from production.models import InvestigationRequest
from production.service import InvestigationService
from production.spreadsheet_provider import SpreadsheetEvidenceProvider


PROJECT_DIR = Path(__file__).parent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Investigate synthetic local rebate data without an API key."
    )
    parser.add_argument("--customer", default="Acme Retail")
    parser.add_argument("--quarter", default="2026-Q2")
    args = parser.parse_args()

    print("Step 1: Read the synthetic local spreadsheets. No OpenAI API call is made.")
    provider = SpreadsheetEvidenceProvider(PROJECT_DIR)
    try:
        tenant = provider.tenant_for_customer(args.customer)
        request = InvestigationRequest(
            request_id=f"DEMO-{uuid4()}",
            tenant_id=tenant,
            actor_id="local-demo-user",
            actor_roles={"investigator"},
            customer=args.customer,
            quarter=args.quarter,
            customer_scope={args.customer},
        )
        print("Step 2: Check the demo role and customer scope before retrieving evidence.")
        service = InvestigationService(
            provider=provider,
            audit_log=AuditLog(PROJECT_DIR / "local_data" / "audit.jsonl"),
        )
        print("Step 3: Apply versioned rules and exact decimal arithmetic.")
        result = service.investigate(request)
    except (LookupError, ValueError, PermissionError, OSError) as error:
        print(f"Investigation could not finish: {error}", file=sys.stderr)
        return 1

    print("Step 4: Show the structured result and record a local audit event.\n")
    print(result.model_dump_json(indent=2))
    if result.human_review:
        print("\nA person must review this case before it can be closed.")
    else:
        print("\nThe deterministic rules completed this case.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
