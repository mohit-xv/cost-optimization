"""Phase 2 — orphaned / old EBS snapshots."""
import pytest
from botocore.exceptions import ClientError

from common import dynamo
from common.models import FindingStatus, ResourceType
from execute.handler import execute
from findings.handler import approve
from scan.handler import run_scan

SNAP = ResourceType.EBS_SNAPSHOT.value


def _by_type(resource_type: str):
    return [f for f in dynamo.list_findings() if f.resource_type == resource_type]


def _make_orphan_snapshot(ec2, size=200) -> str:
    vol = ec2.create_volume(AvailabilityZone="us-east-1a", Size=size, VolumeType="gp3")[
        "VolumeId"
    ]
    snap = ec2.create_snapshot(VolumeId=vol)["SnapshotId"]
    ec2.delete_volume(VolumeId=vol)  # orphan it: source volume gone
    return snap


def test_scan_flags_orphaned_snapshot(register_account, ec2):
    register_account()
    snap = _make_orphan_snapshot(ec2, size=200)

    run_scan()

    snaps = _by_type(SNAP)
    assert len(snaps) == 1
    assert snaps[0].resource_id == snap
    assert snaps[0].monthly_burn == round(200 * 0.05, 4)  # 10.0
    assert snaps[0].metadata["orphaned"] is True


def test_scan_skips_snapshot_backing_ami(register_account, ec2):
    register_account()
    iid = ec2.run_instances(ImageId="ami-12345678", MinCount=1, MaxCount=1)[
        "Instances"
    ][0]["InstanceId"]
    # create_image produces a backing snapshot whose source volume no longer exists
    # (orphaned) -> it WOULD be flagged, but must be skipped because an AMI references it.
    ec2.create_image(InstanceId=iid, Name="cost-killer-test-ami")

    run_scan()

    assert _by_type(SNAP) == []


def test_execute_deletes_orphaned_snapshot(register_account, ec2):
    register_account()
    snap = _make_orphan_snapshot(ec2)
    run_scan()
    finding = _by_type(SNAP)[0]
    approve(finding.finding_id)

    out = execute([finding.finding_id], dry_run=False, actor="t@example.com")

    assert out["deleted"] == 1
    assert out["results"][0]["status"] == "DELETED"
    with pytest.raises(ClientError):
        ec2.describe_snapshots(SnapshotIds=[snap])
    assert dynamo.get_finding(finding.finding_id).status == FindingStatus.DELETED.value
