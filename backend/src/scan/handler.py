"""Discovery (scan) Lambda — read-only.

MVP: finds unattached EBS volumes across registered target accounts/regions, computes
monthly cash burn from the cached pricing matrix, ranks with pandas, and upserts findings
as ``PENDING_APPROVAL``. Makes zero mutating calls.

Invoke async (EventBridge schedule or API 202) with an optional event:
    {"accountId": "...", "regions": ["us-east-1"], "scanId": "..."}
With no accountId it scans all enabled registered accounts.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

import pandas as pd

from common import config, dynamo, pricing, sts_assume
from common.guardrails import is_protected
from common.models import Finding, ResourceType, make_finding_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _last_detach_time(account, region: str, volume_id: str):
    """Best-effort most-recent DetachVolume/CreateVolume time from CloudTrail."""
    try:
        ct = sts_assume.scan_client("cloudtrail", account, region)
        resp = ct.lookup_events(
            LookupAttributes=[
                {"AttributeKey": "ResourceName", "AttributeValue": volume_id}
            ],
            MaxResults=10,
        )
        for event in resp.get("Events", []):
            if event.get("EventName") in ("DetachVolume", "CreateVolume"):
                return event.get("EventTime")
    except Exception:
        return None
    return None


def _volume_idle_days(account, region: str, vol: dict) -> int:
    ref = _last_detach_time(account, region, vol["VolumeId"]) or vol.get("CreateTime")
    if ref is None:
        return 0
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    return max(0, (_now() - ref).days)


def _scan_account_region(account, region: str) -> list[dict]:
    """Candidate unattached EBS volumes for one account+region (after guardrails)."""
    ec2 = sts_assume.scan_client("ec2", account, region)
    candidates: list[dict] = []
    paginator = ec2.get_paginator("describe_volumes")
    for page in paginator.paginate(
        Filters=[{"Name": "status", "Values": ["available"]}]
    ):
        for vol in page.get("Volumes", []):
            protected, _reason = is_protected(vol.get("Tags", []))
            if protected:
                continue
            days_idle = _volume_idle_days(account, region, vol)
            if days_idle < config.idle_days_threshold():
                continue
            vtype = vol.get("VolumeType", "gp2")
            size = vol.get("Size", 0)
            iops = vol.get("Iops", 0) or 0
            candidates.append(
                {
                    "accountId": account.account_id,
                    "region": region,
                    "resourceId": vol["VolumeId"],
                    "resourceType": ResourceType.EBS_VOLUME.value,
                    "sizeGb": int(size),
                    "volumeType": vtype,
                    "iops": int(iops),
                    "daysIdle": int(days_idle),
                    "monthlyBurn": pricing.ebs_monthly_burn(size, vtype, region, iops),
                }
            )
    return candidates


def run_scan(event: dict | None = None) -> dict:
    event = event or {}
    scan_id = event.get("scanId") or str(uuid.uuid4())

    if event.get("accountId"):
        acct = dynamo.get_account(event["accountId"])
        accounts = [acct] if acct else []
    else:
        accounts = [a for a in dynamo.list_accounts() if a.enabled]

    rows: list[dict] = []
    scanned = 0
    for account in accounts:
        regions = event.get("regions") or account.regions or config.default_regions()
        for region in regions:
            scanned += 1
            rows.extend(_scan_account_region(account, region))

    flagged = 0
    total_burn = 0.0
    if rows:
        # pandas: dedupe and rank candidates by monthly burn before persisting.
        df = pd.DataFrame(rows).drop_duplicates(
            subset=["accountId", "region", "resourceId"]
        )
        df = df.sort_values("monthlyBurn", ascending=False)
        for rec in df.to_dict("records"):
            monthly = float(rec["monthlyBurn"])
            finding = Finding(
                finding_id=make_finding_id(
                    rec["accountId"], rec["region"], rec["resourceId"]
                ),
                account_id=rec["accountId"],
                region=rec["region"],
                resource_id=rec["resourceId"],
                resource_type=rec["resourceType"],
                days_idle=int(rec["daysIdle"]),
                monthly_burn=monthly,
                daily_burn=round(monthly / 30.0, 4),
                metadata={
                    "sizeGb": int(rec["sizeGb"]),
                    "volumeType": rec["volumeType"],
                    "iops": int(rec["iops"]),
                },
                scan_id=scan_id,
            )
            if dynamo.upsert_pending_finding(finding) == "upserted":
                flagged += 1
                total_burn += monthly

    summary = {
        "scanId": scan_id,
        "scannedAccountRegions": scanned,
        "flagged": flagged,
        "totalMonthlyBurn": round(total_burn, 2),
        "timestamp": int(time.time()),
    }
    print(f"scan complete: {summary}")
    return summary


def handler(event, context):
    """Entry point for both EventBridge (raw event) and API Gateway (/scan POST)."""
    event = event or {}
    is_http = "httpMethod" in event or "requestContext" in event
    if is_http:
        from common.http import parse_body, response

        summary = run_scan(parse_body(event))
        return response(200, summary)
    return run_scan(event)
