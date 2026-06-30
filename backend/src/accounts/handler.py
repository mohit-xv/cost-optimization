"""Target-account registry API Lambda.

Routes (API Gateway REST proxy):
    GET    /accounts          -> list registered target accounts
    POST   /accounts          -> create/update an account
    DELETE /accounts/{id}     -> remove an account
"""
from __future__ import annotations

from common import dynamo
from common.http import parse_body, response
from common.models import Account


def upsert_account(payload: dict) -> Account:
    account = Account(
        account_id=str(payload["accountId"]),
        name=payload.get("name", ""),
        external_id=payload.get("externalId", ""),
        regions=list(payload.get("regions", [])),
        scan_role_arn=payload.get("scanRoleArn"),
        exec_role_arn=payload.get("execRoleArn"),
        enabled=bool(payload.get("enabled", True)),
    )
    dynamo.put_account(account)
    return account


def handler(event, context):
    method = event.get("httpMethod")
    path_params = event.get("pathParameters") or {}
    try:
        if method == "GET":
            return response(
                200, {"accounts": [a.to_json() for a in dynamo.list_accounts()]}
            )
        if method == "POST":
            payload = parse_body(event)
            if not payload.get("accountId"):
                return response(400, {"error": "accountId is required"})
            account = upsert_account(payload)
            return response(200, account.to_json())
        if method == "DELETE":
            account_id = path_params.get("id")
            if not account_id:
                return response(400, {"error": "missing account id"})
            dynamo.delete_account(account_id)
            return response(200, {"accountId": account_id, "deleted": True})
        return response(405, {"error": "method not allowed"})
    except Exception as exc:  # noqa: BLE001
        print(f"accounts handler error: {exc}")
        return response(500, {"error": str(exc)})
