"""Findings API Lambda.

Routes (API Gateway REST proxy):
    GET    /findings?status=&accountId=   -> list findings + dashboard summary
    POST   /findings/{id}/approve         -> PENDING_APPROVAL -> APPROVED
    POST   /findings/{id}/ignore          -> PENDING_APPROVAL -> IGNORED

Approve/ignore use a conditional write, so they fail with 409 if the finding is no longer
PENDING_APPROVAL (prevents double-approval / stale-UI actions).
"""
from __future__ import annotations

from common import dynamo
from common.http import response
from common.models import FindingStatus


def list_findings_response(status=None, account_id=None) -> dict:
    findings = dynamo.list_findings(status=status, account_id=account_id)
    total_monthly = round(sum(f.monthly_burn for f in findings), 2)
    accounts = sorted({f.account_id for f in findings})
    return {
        "findings": [f.to_json() for f in findings],
        "summary": {
            "totalMonthlyWaste": total_monthly,
            "totalFlagged": len(findings),
            "activeAccounts": len(accounts),
            "accounts": accounts,
        },
    }


def approve(finding_id: str) -> bool:
    return dynamo.transition_status(
        finding_id,
        FindingStatus.PENDING_APPROVAL.value,
        FindingStatus.APPROVED.value,
    )


def ignore(finding_id: str) -> bool:
    return dynamo.transition_status(
        finding_id,
        FindingStatus.PENDING_APPROVAL.value,
        FindingStatus.IGNORED.value,
    )


def handler(event, context):
    method = event.get("httpMethod")
    path = event.get("path", "") or ""
    params = event.get("queryStringParameters") or {}
    path_params = event.get("pathParameters") or {}
    try:
        if method == "GET":
            return response(
                200,
                list_findings_response(params.get("status"), params.get("accountId")),
            )
        if method == "POST":
            finding_id = path_params.get("id")
            if not finding_id:
                return response(400, {"error": "missing finding id"})
            if path.endswith("/approve"):
                ok = approve(finding_id)
            elif path.endswith("/ignore"):
                ok = ignore(finding_id)
            else:
                return response(400, {"error": "unknown action"})
            if ok:
                return response(200, {"findingId": finding_id, "updated": True})
            return response(
                409,
                {
                    "findingId": finding_id,
                    "updated": False,
                    "error": "state conflict — finding is not PENDING_APPROVAL",
                },
            )
        return response(405, {"error": "method not allowed"})
    except Exception as exc:  # noqa: BLE001
        print(f"findings handler error: {exc}")
        return response(500, {"error": str(exc)})
