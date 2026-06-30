"""Phase 2 — unassociated Elastic IPs and idle NAT Gateways."""
import pytest
from botocore.exceptions import ClientError

from common import dynamo
from common.models import FindingStatus, ResourceType
from execute.handler import execute
from findings.handler import approve
from scan.handler import run_scan

EIP = ResourceType.ELASTIC_IP.value
NAT = ResourceType.NAT_GATEWAY.value


def _by_type(resource_type: str):
    return [f for f in dynamo.list_findings() if f.resource_type == resource_type]


def _make_nat(ec2) -> str:
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
    subnet = ec2.create_subnet(VpcId=vpc, CidrBlock="10.0.1.0/24")["Subnet"]["SubnetId"]
    alloc = ec2.allocate_address(Domain="vpc")["AllocationId"]
    return ec2.create_nat_gateway(SubnetId=subnet, AllocationId=alloc)["NatGateway"][
        "NatGatewayId"
    ]


# --- Elastic IP ------------------------------------------------------------------
def test_scan_flags_unassociated_eip(register_account, ec2):
    register_account()
    alloc = ec2.allocate_address(Domain="vpc")["AllocationId"]

    run_scan()

    eips = _by_type(EIP)
    assert len(eips) == 1
    assert eips[0].resource_id == alloc
    assert eips[0].monthly_burn == round(0.005 * 730, 4)


def test_scan_skips_associated_eip(register_account, ec2):
    register_account()
    alloc = ec2.allocate_address(Domain="vpc")["AllocationId"]
    inst = ec2.run_instances(ImageId="ami-12345678", MinCount=1, MaxCount=1)[
        "Instances"
    ][0]["InstanceId"]
    ec2.associate_address(AllocationId=alloc, InstanceId=inst)

    run_scan()

    assert _by_type(EIP) == []


def test_execute_releases_eip(register_account, ec2):
    register_account()
    alloc = ec2.allocate_address(Domain="vpc")["AllocationId"]
    run_scan()
    finding = _by_type(EIP)[0]
    approve(finding.finding_id)

    out = execute([finding.finding_id], dry_run=False, actor="t@example.com")

    assert out["deleted"] == 1
    assert out["results"][0]["status"] == "DELETED"
    with pytest.raises(ClientError):
        ec2.describe_addresses(AllocationIds=[alloc])
    assert dynamo.get_finding(finding.finding_id).status == FindingStatus.DELETED.value


def test_eip_dry_run_keeps_it(register_account, ec2):
    register_account()
    alloc = ec2.allocate_address(Domain="vpc")["AllocationId"]
    run_scan()
    finding = _by_type(EIP)[0]
    approve(finding.finding_id)

    out = execute([finding.finding_id], dry_run=True)

    assert out["results"][0]["status"] == "DRY_RUN_OK"
    assert ec2.describe_addresses(AllocationIds=[alloc])["Addresses"]
    assert dynamo.get_finding(finding.finding_id).status == FindingStatus.APPROVED.value


# --- NAT Gateway -----------------------------------------------------------------
def test_scan_flags_idle_nat(register_account, ec2):
    register_account()
    nat_id = _make_nat(ec2)

    run_scan()

    nats = _by_type(NAT)
    assert len(nats) == 1
    assert nats[0].resource_id == nat_id
    assert nats[0].monthly_burn == round(0.045 * 730, 4)


def test_execute_deletes_nat(register_account, ec2):
    register_account()
    nat_id = _make_nat(ec2)
    run_scan()
    finding = _by_type(NAT)[0]
    approve(finding.finding_id)

    out = execute([finding.finding_id], dry_run=False, actor="t@example.com")

    assert out["deleted"] == 1
    assert out["results"][0]["status"] == "DELETED"
    state = ec2.describe_nat_gateways(NatGatewayIds=[nat_id])["NatGateways"][0]["State"]
    assert state in ("deleted", "deleting")
    assert dynamo.get_finding(finding.finding_id).status == FindingStatus.DELETED.value
