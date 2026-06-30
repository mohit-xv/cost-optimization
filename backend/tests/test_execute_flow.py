"""End-to-end Discovery -> Approve -> Execute flow, incl. dry-run and TOCTOU guard."""
import pytest
from botocore.exceptions import ClientError

from common import dynamo
from common.models import FindingStatus
from execute.handler import execute
from findings.handler import approve
from scan.handler import run_scan


def _scan_one(register_account, make_volume, **kw):
    register_account()
    volume_id = make_volume(**kw)
    run_scan()
    return dynamo.list_findings()[0], volume_id


def test_approve_then_double_approve_conflicts(register_account, make_volume):
    finding, _ = _scan_one(register_account, make_volume)
    assert approve(finding.finding_id) is True
    assert approve(finding.finding_id) is False  # no longer PENDING_APPROVAL


def test_execute_deletes_approved_volume(register_account, make_volume, ec2):
    finding, volume_id = _scan_one(register_account, make_volume)
    approve(finding.finding_id)

    out = execute([finding.finding_id], dry_run=False, actor="tester@example.com")

    assert out["deleted"] == 1
    result = out["results"][0]
    assert result["status"] == "DELETED"
    assert result["receipt"]
    assert result["snapshotId"]
    # the live volume is gone
    with pytest.raises(ClientError):
        ec2.describe_volumes(VolumeIds=[volume_id])
    assert dynamo.get_finding(finding.finding_id).status == FindingStatus.DELETED.value


def test_dry_run_makes_no_changes(register_account, make_volume, ec2):
    finding, volume_id = _scan_one(register_account, make_volume)
    approve(finding.finding_id)

    out = execute([finding.finding_id], dry_run=True)

    assert out["deleted"] == 0
    assert out["results"][0]["status"] == "DRY_RUN_OK"
    # volume untouched, finding still APPROVED
    assert ec2.describe_volumes(VolumeIds=[volume_id])["Volumes"][0]["State"] == "available"
    assert dynamo.get_finding(finding.finding_id).status == FindingStatus.APPROVED.value


def test_execute_skips_unapproved(register_account, make_volume):
    finding, _ = _scan_one(register_account, make_volume)  # still PENDING_APPROVAL

    out = execute([finding.finding_id], dry_run=False)

    assert out["deleted"] == 0
    assert out["results"][0]["status"] == "SKIPPED"


def test_unhandled_deleter_error_marks_failed_not_stuck(register_account, make_volume, monkeypatch):
    finding, _ = _scan_one(register_account, make_volume)
    approve(finding.finding_id)

    import execute.handler as ex

    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated AWS failure")

    monkeypatch.setitem(ex._DELETERS, "EBS_VOLUME", boom)

    out = ex.execute([finding.finding_id], dry_run=False)

    assert out["deleted"] == 0
    assert out["results"][0]["status"] == "FAILED"
    # the finding must not be stuck in DELETING
    assert dynamo.get_finding(finding.finding_id).status == FindingStatus.FAILED.value


def test_toctou_reattached_volume_aborts(register_account, make_volume, ec2):
    finding, volume_id = _scan_one(register_account, make_volume)
    approve(finding.finding_id)

    # Simulate the volume being re-attached between approval and execution.
    inst = ec2.run_instances(ImageId="ami-12345678", MinCount=1, MaxCount=1)
    iid = inst["Instances"][0]["InstanceId"]
    ec2.attach_volume(VolumeId=volume_id, InstanceId=iid, Device="/dev/sdf")

    out = execute([finding.finding_id], dry_run=False)

    assert out["deleted"] == 0
    assert out["results"][0]["status"] == "ABORTED"
    # volume survived; finding marked FAILED, not DELETED
    assert ec2.describe_volumes(VolumeIds=[volume_id])["Volumes"][0]["State"] == "in-use"
    assert dynamo.get_finding(finding.finding_id).status == FindingStatus.FAILED.value
