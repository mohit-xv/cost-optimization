"""Discovery (scan) Lambda — read-only.

Detects waste across registered target accounts/regions and upserts findings as
``PENDING_APPROVAL``. Makes zero mutating calls.

Resource types:
  - Unattached EBS volumes        (state=available >= IDLE_DAYS_THRESHOLD days)
  - Unassociated Elastic IPs      (no association)
  - Idle NAT Gateways             (≈0 bytes processed over the metric window)

Invoke async (EventBridge schedule or API 202) with an optional event:
    {"accountId": "...", "regions": ["us-east-1"], "scanId": "..."}
With no accountId it scans all enabled registered accounts.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone

import pandas as pd

from common import config, dynamo, pricing, sts_assume
from common.guardrails import is_protected
from common.models import Finding, ResourceType, make_finding_id

_NAT_METRIC_WINDOW_DAYS = 14
_NAT_IDLE_BYTES = 1_000_000  # < ~1 MB processed over the window => idle


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Unattached EBS volumes -------------------------------------------------------
def _last_detach_time(account, region: str, volume_id: str):
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


def _scan_ebs(account, region: str) -> list[dict]:
    ec2 = sts_assume.scan_client("ec2", account, region)
    out: list[dict] = []
    paginator = ec2.get_paginator("describe_volumes")
    for page in paginator.paginate(
        Filters=[{"Name": "status", "Values": ["available"]}]
    ):
        for vol in page.get("Volumes", []):
            protected, _ = is_protected(vol.get("Tags", []))
            if protected:
                continue
            days_idle = _volume_idle_days(account, region, vol)
            if days_idle < config.idle_days_threshold():
                continue
            vtype = vol.get("VolumeType", "gp2")
            size = vol.get("Size", 0)
            iops = vol.get("Iops", 0) or 0
            out.append(
                _candidate(
                    account,
                    region,
                    vol["VolumeId"],
                    ResourceType.EBS_VOLUME.value,
                    days_idle,
                    pricing.ebs_monthly_burn(size, vtype, region, iops),
                    {"sizeGb": int(size), "volumeType": vtype, "iops": int(iops)},
                )
            )
    return out


# --- Unassociated Elastic IPs -----------------------------------------------------
def _scan_eips(account, region: str) -> list[dict]:
    ec2 = sts_assume.scan_client("ec2", account, region)
    out: list[dict] = []
    for addr in ec2.describe_addresses().get("Addresses", []):
        if addr.get("AssociationId") or addr.get("InstanceId") or addr.get("NetworkInterfaceId"):
            continue  # currently associated -> in use
        protected, _ = is_protected(addr.get("Tags", []))
        if protected:
            continue
        resource_id = addr.get("AllocationId") or addr.get("PublicIp")
        out.append(
            _candidate(
                account,
                region,
                resource_id,
                ResourceType.ELASTIC_IP.value,
                0,
                pricing.eip_monthly_burn(),
                {"publicIp": addr.get("PublicIp"), "allocationId": addr.get("AllocationId")},
            )
        )
    return out


# --- Idle NAT Gateways ------------------------------------------------------------
def _nat_is_idle(account, region: str, nat_id: str) -> bool:
    """True if the NAT Gateway processed ~no bytes over the metric window."""
    try:
        cw = sts_assume.scan_client("cloudwatch", account, region)
        end = _now()
        start = end - timedelta(days=_NAT_METRIC_WINDOW_DAYS)
        resp = cw.get_metric_data(
            MetricDataQueries=[
                {
                    "Id": "out",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/NATGateway",
                            "MetricName": "BytesOutToDestination",
                            "Dimensions": [{"Name": "NatGatewayId", "Value": nat_id}],
                        },
                        "Period": 86400,
                        "Stat": "Sum",
                    },
                }
            ],
            StartTime=start,
            EndTime=end,
        )
        values = resp.get("MetricDataResults", [{}])[0].get("Values", [])
        return sum(values) < _NAT_IDLE_BYTES
    except Exception:
        # Be conservative: if metrics can't be read, do NOT flag (avoid false deletes).
        return False


def _scan_nat_gateways(account, region: str) -> list[dict]:
    ec2 = sts_assume.scan_client("ec2", account, region)
    out: list[dict] = []
    resp = ec2.describe_nat_gateways()
    gateways = list(resp.get("NatGateways", []))
    while resp.get("NextToken"):
        resp = ec2.describe_nat_gateways(NextToken=resp["NextToken"])
        gateways.extend(resp.get("NatGateways", []))

    for nat in gateways:
        if nat.get("State") != "available":
            continue
        protected, _ = is_protected(nat.get("Tags", []))
        if protected:
            continue
        nat_id = nat["NatGatewayId"]
        if not _nat_is_idle(account, region, nat_id):
            continue
        out.append(
            _candidate(
                account,
                region,
                nat_id,
                ResourceType.NAT_GATEWAY.value,
                _NAT_METRIC_WINDOW_DAYS,
                pricing.nat_gateway_monthly_burn(region),
                {"subnetId": nat.get("SubnetId"), "vpcId": nat.get("VpcId")},
            )
        )
    return out


def _scan_snapshots(account, region: str) -> list[dict]:
    ec2 = sts_assume.scan_client("ec2", account, region)

    # Existing volume ids (so we can tell which snapshots are orphaned).
    existing_volumes: set[str] = set()
    vol_paginator = ec2.get_paginator("describe_volumes")
    for page in vol_paginator.paginate():
        for vol in page.get("Volumes", []):
            existing_volumes.add(vol["VolumeId"])

    # Snapshot ids backing self-owned AMIs must never be deleted (would break the AMI).
    ami_snapshot_ids: set[str] = set()
    for img in ec2.describe_images(Owners=["self"]).get("Images", []):
        for bdm in img.get("BlockDeviceMappings", []):
            sid = bdm.get("Ebs", {}).get("SnapshotId")
            if sid:
                ami_snapshot_ids.add(sid)

    retention = config.snapshot_retention_days()
    out: list[dict] = []
    snap_paginator = ec2.get_paginator("describe_snapshots")
    for page in snap_paginator.paginate(OwnerIds=["self"]):
        for snap in page.get("Snapshots", []):
            snap_id = snap["SnapshotId"]
            if snap_id in ami_snapshot_ids:
                continue
            protected, _ = is_protected(snap.get("Tags", []))
            if protected:
                continue
            source_vol = snap.get("VolumeId")
            orphaned = bool(source_vol) and source_vol not in existing_volumes
            start = snap.get("StartTime")
            age = 0
            if start is not None:
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                age = max(0, (_now() - start).days)
            # Flag if the source volume is gone, or the snapshot is older than retention.
            if not orphaned and age <= retention:
                continue
            size = snap.get("VolumeSize", 0)
            out.append(
                _candidate(
                    account,
                    region,
                    snap_id,
                    ResourceType.EBS_SNAPSHOT.value,
                    age,
                    pricing.snapshot_monthly_burn(size, region),
                    {"volumeSize": int(size), "sourceVolumeId": source_vol, "orphaned": orphaned},
                )
            )
    return out


def _candidate(account, region, resource_id, resource_type, days_idle, monthly_burn, metadata) -> dict:
    return {
        "accountId": account.account_id,
        "region": region,
        "resourceId": resource_id,
        "resourceType": resource_type,
        "daysIdle": int(days_idle),
        "monthlyBurn": float(monthly_burn),
        "metadata": metadata,
    }


def _scan_account_region(account, region: str) -> list[dict]:
    return (
        _scan_ebs(account, region)
        + _scan_eips(account, region)
        + _scan_nat_gateways(account, region)
        + _scan_snapshots(account, region)
    )


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
                metadata=rec["metadata"],
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
