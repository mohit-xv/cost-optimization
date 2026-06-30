"""DynamoDB data-access layer.

Tables (all in the central account):
- Findings      PK=findingId                  — the state machine
- Accounts      PK=accountId                  — target-account registry
- ExecutionLog  PK=findingId, SK=ts (Number)  — tamper-evident deletion receipts
- PricingMatrix PK=pk                          — cached Price List rates
"""
from __future__ import annotations

import time
from typing import Optional

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from common import config
from common.models import Account, Finding, PROTECTED_FROM_RESCAN
from common.serde import to_dynamo

_RESOURCE = None


def _ddb():
    global _RESOURCE
    if _RESOURCE is None:
        _RESOURCE = boto3.resource("dynamodb")
    return _RESOURCE


def _table(name: str):
    return _ddb().Table(name)


# --- Findings ---------------------------------------------------------------------
def put_finding(finding: Finding) -> None:
    _table(config.findings_table()).put_item(Item=finding.to_item())


def get_finding(finding_id: str) -> Optional[Finding]:
    resp = _table(config.findings_table()).get_item(Key={"findingId": finding_id})
    item = resp.get("Item")
    return Finding.from_item(item) if item else None


def list_findings(status: Optional[str] = None, account_id: Optional[str] = None) -> list[Finding]:
    table = _table(config.findings_table())
    filt = None
    if status:
        filt = Attr("status").eq(status)
    if account_id:
        cond = Attr("accountId").eq(account_id)
        filt = cond if filt is None else filt & cond

    kwargs: dict = {}
    if filt is not None:
        kwargs["FilterExpression"] = filt

    items: list[dict] = []
    resp = table.scan(**kwargs)
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
    return [Finding.from_item(i) for i in items]


def upsert_pending_finding(finding: Finding) -> str:
    """Insert/refresh a PENDING_APPROVAL finding without clobbering human/terminal states.

    Returns ``"skipped"`` if an existing finding is already approved/deleting/deleted/
    ignored, otherwise ``"upserted"``.
    """
    existing = get_finding(finding.finding_id)
    if existing and existing.status in PROTECTED_FROM_RESCAN:
        return "skipped"
    put_finding(finding)
    return "upserted"


def transition_status(
    finding_id: str,
    expected: str,
    new_status: str,
    extra: Optional[dict] = None,
) -> bool:
    """Atomically move a finding from ``expected`` to ``new_status`` (optimistic lock).

    Returns False if the current status no longer matches ``expected``.
    """
    table = _table(config.findings_table())
    names = {"#s": "status"}
    values = {":expected": expected, ":new": new_status, ":ts": int(time.time())}
    set_parts = ["#s = :new", "updatedAt = :ts"]
    if extra:
        for i, (key, val) in enumerate(extra.items()):
            nk, vk = f"#k{i}", f":v{i}"
            names[nk] = key
            values[vk] = to_dynamo(val)
            set_parts.append(f"{nk} = {vk}")
    try:
        table.update_item(
            Key={"findingId": finding_id},
            UpdateExpression="SET " + ", ".join(set_parts),
            ConditionExpression="#s = :expected",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


# --- Execution log (receipts) -----------------------------------------------------
def put_execution_log(entry: dict) -> None:
    _table(config.execution_log_table()).put_item(Item=to_dynamo(entry))


# --- Accounts ---------------------------------------------------------------------
def put_account(account: Account) -> None:
    _table(config.accounts_table()).put_item(Item=to_dynamo(account.to_item()))


def get_account(account_id: str) -> Optional[Account]:
    resp = _table(config.accounts_table()).get_item(Key={"accountId": account_id})
    item = resp.get("Item")
    return Account.from_item(item) if item else None


def list_accounts() -> list[Account]:
    table = _table(config.accounts_table())
    items: list[dict] = []
    resp = table.scan()
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))
    return [Account.from_item(i) for i in items]


def delete_account(account_id: str) -> None:
    _table(config.accounts_table()).delete_item(Key={"accountId": account_id})


# --- Pricing matrix ---------------------------------------------------------------
def get_pricing_item(pk: str) -> Optional[dict]:
    resp = _table(config.pricing_table()).get_item(Key={"pk": pk})
    return resp.get("Item")


def put_pricing_item(item: dict) -> None:
    _table(config.pricing_table()).put_item(Item=to_dynamo(item))
