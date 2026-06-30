"""Execution Lambda — the deletion barrier (high privilege).

For each APPROVED finding it:
  1. requires DynamoDB state == APPROVED (skips otherwise),
  2. locks APPROVED -> DELETING with a conditional write (idempotent, no double-delete),
  3. TOCTOU re-verifies the live resource still matches its idle criteria,
  4. re-checks guardrails against live tags,
  5. runs a boto3 DryRun,
  6. snapshots-before-delete (recoverable) then deletes,
  7. records DELETED + a SHA-256 receipt in ExecutionLog.

``dryRun: true`` performs steps 3-5 only (read-only preview) and never mutates state.
"""
from __future__ import annotations

import hashlib
import json
import time

from botocore.exceptions import ClientError

from common import dynamo, sts_assume
from common.guardrails import is_protected
from common.http import actor_from_event, parse_body, response
from common.models import FindingStatus, ResourceType

# AWS error codes that mean "blocked by native protection" rather than a transient error.
_NATIVE_PROTECTION_CODES = {
    "OperationNotPermitted",          # e.g. CloudFormation termination protection / deletion protection
    "TerminationProtection",
    "VolumeInUse",
    "InvalidVolume.ProtectedSnapshot",
    "SnapshotLocked",                 # AWS Backup Vault Lock (WORM)
}


def _receipt(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _dry_run_delete_volume(ec2, volume_id: str) -> tuple[bool, str]:
    """Validate the delete with EC2 DryRun. Returns (allowed, message)."""
    try:
        ec2.delete_volume(VolumeId=volume_id, DryRun=True)
        return True, "dry_run_no_exception"
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "DryRunOperation":
            return True, "dry_run_ok"
        if code == "UnauthorizedOperation":
            return False, "unauthorized"
        return False, code


def _reverify_volume(ec2, volume_id: str):
    """TOCTOU guard. Returns (ok, reason, live_tags)."""
    try:
        resp = ec2.describe_volumes(VolumeIds=[volume_id])
    except ClientError as exc:
        if exc.response["Error"]["Code"] in (
            "InvalidVolume.NotFound",
            "InvalidVolumeID.NotFound",
        ):
            return False, "already_deleted", []
        raise
    vols = resp.get("Volumes", [])
    if not vols:
        return False, "already_deleted", []
    vol = vols[0]
    if vol.get("State") != "available":
        return False, f"state_changed:{vol.get('State')}", vol.get("Tags", [])
    if vol.get("Attachments"):
        return False, "reattached", vol.get("Tags", [])
    return True, "ok", vol.get("Tags", [])


def _delete_ebs_volume(account, finding, dry_run: bool, actor: str) -> dict:
    ec2 = sts_assume.exec_client("ec2", account, finding.region)
    volume_id = finding.resource_id

    ok, reason, tags = _reverify_volume(ec2, volume_id)
    if not ok:
        return {"findingId": finding.finding_id, "status": "ABORTED", "reason": reason}

    protected, preason = is_protected(tags)
    if protected:
        return {"findingId": finding.finding_id, "status": "ABORTED", "reason": preason}

    allowed, msg = _dry_run_delete_volume(ec2, volume_id)
    if not allowed:
        return {"findingId": finding.finding_id, "status": "ABORTED", "reason": msg}

    if dry_run:
        return {"findingId": finding.finding_id, "status": "DRY_RUN_OK", "reason": msg}

    snapshot_id = None
    try:
        snap = ec2.create_snapshot(
            VolumeId=volume_id,
            Description=f"cost-killer pre-delete snapshot of {volume_id}",
        )
        snapshot_id = snap.get("SnapshotId")
        ec2.delete_volume(VolumeId=volume_id)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        status = "IGNORED" if code in _NATIVE_PROTECTION_CODES else "FAILED"
        return {
            "findingId": finding.finding_id,
            "status": status,
            "reason": code,
            "snapshotId": snapshot_id,
        }

    ts = int(time.time())
    receipt = _receipt(
        {
            "resourceId": volume_id,
            "action": "delete_volume",
            "actor": actor,
            "ts": ts,
            "priorState": FindingStatus.APPROVED.value,
            "snapshotId": snapshot_id,
        }
    )
    dynamo.put_execution_log(
        {
            "findingId": finding.finding_id,
            "ts": ts,
            "accountId": finding.account_id,
            "region": finding.region,
            "resourceId": volume_id,
            "action": "delete_volume",
            "actor": actor,
            "snapshotId": snapshot_id,
            "receipt": receipt,
        }
    )
    return {
        "findingId": finding.finding_id,
        "status": "DELETED",
        "snapshotId": snapshot_id,
        "receipt": receipt,
    }


# resource type -> deletion function
_DELETERS = {ResourceType.EBS_VOLUME.value: _delete_ebs_volume}


def execute(finding_ids, dry_run: bool = False, actor: str = "unknown") -> dict:
    results = []
    for finding_id in finding_ids:
        finding = dynamo.get_finding(finding_id)
        if finding is None:
            results.append({"findingId": finding_id, "status": "NOT_FOUND"})
            continue
        if finding.status != FindingStatus.APPROVED.value:
            results.append(
                {
                    "findingId": finding_id,
                    "status": "SKIPPED",
                    "reason": f"not approved ({finding.status})",
                }
            )
            continue

        account = dynamo.get_account(finding.account_id)
        if account is None:
            results.append(
                {
                    "findingId": finding_id,
                    "status": "FAILED",
                    "reason": "account not registered",
                }
            )
            continue

        deleter = _DELETERS.get(finding.resource_type)
        if deleter is None:
            results.append(
                {
                    "findingId": finding_id,
                    "status": "SKIPPED",
                    "reason": f"unsupported type {finding.resource_type}",
                }
            )
            continue

        # Dry-run preview is read-only — no state transition.
        if dry_run:
            results.append(deleter(account, finding, True, actor))
            continue

        # Lock APPROVED -> DELETING (idempotency: a retry can't double-delete).
        if not dynamo.transition_status(
            finding_id, FindingStatus.APPROVED.value, FindingStatus.DELETING.value
        ):
            results.append(
                {
                    "findingId": finding_id,
                    "status": "SKIPPED",
                    "reason": "lock failed (already executing/deleted)",
                }
            )
            continue

        result = deleter(account, finding, False, actor)
        if result["status"] == "DELETED":
            dynamo.transition_status(
                finding_id,
                FindingStatus.DELETING.value,
                FindingStatus.DELETED.value,
                extra={
                    "snapshotId": result.get("snapshotId"),
                    "receipt": result.get("receipt"),
                },
            )
        elif result["status"] == "IGNORED":
            dynamo.transition_status(
                finding_id,
                FindingStatus.DELETING.value,
                FindingStatus.IGNORED.value,
                extra={"failureReason": result.get("reason", "native_protection")},
            )
        else:
            dynamo.transition_status(
                finding_id,
                FindingStatus.DELETING.value,
                FindingStatus.FAILED.value,
                extra={"failureReason": result.get("reason", "unknown")},
            )
        results.append(result)

    deleted = sum(1 for r in results if r["status"] == "DELETED")
    return {"results": results, "deleted": deleted, "requested": len(finding_ids)}


def handler(event, context):
    body = parse_body(event)
    finding_ids = body.get("findingIds", [])
    dry_run = bool(body.get("dryRun", False))
    actor = actor_from_event(event, fallback=body.get("actor", "unknown"))
    try:
        return response(200, execute(finding_ids, dry_run=dry_run, actor=actor))
    except Exception as exc:  # noqa: BLE001
        print(f"execute handler error: {exc}")
        return response(500, {"error": str(exc)})
