"""Discovery engine tests."""
from common import dynamo
from common.models import FindingStatus
from scan.handler import run_scan


def test_scan_flags_unattached_volume(register_account, make_volume):
    register_account()
    volume_id = make_volume(size=100, vtype="gp3")

    summary = run_scan()

    assert summary["flagged"] == 1
    findings = dynamo.list_findings()
    assert len(findings) == 1
    finding = findings[0]
    assert finding.resource_id == volume_id
    assert finding.status == FindingStatus.PENDING_APPROVAL.value
    assert finding.monthly_burn == 8.0
    assert finding.metadata["sizeGb"] == 100
    assert finding.metadata["volumeType"] == "gp3"


def test_scan_skips_protected_volumes(register_account, make_volume):
    register_account()
    make_volume(tags={"CostKiller:Protect": "true"})
    make_volume(tags={"Environment": "production"})
    make_volume(tags={"aws:autoscaling:groupName": "asg-web"})

    summary = run_scan()

    assert summary["flagged"] == 0
    assert dynamo.list_findings() == []


def test_scan_ranks_by_burn(register_account, make_volume):
    register_account()
    make_volume(size=10, vtype="gp3")    # 0.8
    make_volume(size=500, vtype="gp3")   # 40.0
    make_volume(size=100, vtype="gp3")   # 8.0

    run_scan()

    findings = dynamo.list_findings()
    assert len(findings) == 3
    assert max(f.monthly_burn for f in findings) == 40.0


def test_rescan_does_not_clobber_approved(register_account, make_volume):
    register_account()
    make_volume(size=100, vtype="gp3")
    run_scan()
    finding = dynamo.list_findings()[0]
    dynamo.transition_status(
        finding.finding_id,
        FindingStatus.PENDING_APPROVAL.value,
        FindingStatus.APPROVED.value,
    )

    run_scan()  # second discovery pass

    assert dynamo.get_finding(finding.finding_id).status == FindingStatus.APPROVED.value
