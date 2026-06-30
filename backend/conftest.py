"""Pytest fixtures: put ``src`` on the path and stand up a fully mocked AWS environment.

Everything runs against moto — no real AWS calls, nothing is ever deleted for real.
The default moto account is 123456789012; we register that as the target account so the
assumed-role clients and the directly-created test resources share one backend.
"""
from __future__ import annotations

import pathlib
import sys

import boto3
import pytest
from moto import mock_aws

SRC = pathlib.Path(__file__).parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

ACCOUNT_ID = "123456789012"
REGION = "us-east-1"


@pytest.fixture
def env(monkeypatch):
    # moto seeds ~40 default AMIs (and their backing snapshots); disable so
    # describe_snapshots/describe_images only see resources the tests create.
    monkeypatch.setenv("MOTO_EC2_LOAD_DEFAULT_AMIS", "false")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("FINDINGS_TABLE", "test-findings")
    monkeypatch.setenv("ACCOUNTS_TABLE", "test-accounts")
    monkeypatch.setenv("EXECUTION_LOG_TABLE", "test-exec-log")
    monkeypatch.setenv("PRICING_TABLE", "test-pricing")
    monkeypatch.setenv("EXTERNAL_ID", "test-external-id")
    # Threshold 0 so freshly-created mock volumes (CreateTime == now) are flagged.
    monkeypatch.setenv("IDLE_DAYS_THRESHOLD", "0")
    monkeypatch.setenv("DEFAULT_REGIONS", REGION)


@pytest.fixture(autouse=True)
def aws(env):
    with mock_aws():
        from common import dynamo

        dynamo._RESOURCE = None  # rebind cached resource to the active mock
        ddb = boto3.resource("dynamodb", region_name=REGION)
        ddb.create_table(
            TableName="test-findings",
            KeySchema=[{"AttributeName": "findingId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "findingId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        ddb.create_table(
            TableName="test-accounts",
            KeySchema=[{"AttributeName": "accountId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "accountId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        ddb.create_table(
            TableName="test-exec-log",
            KeySchema=[
                {"AttributeName": "findingId", "KeyType": "HASH"},
                {"AttributeName": "ts", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "findingId", "AttributeType": "S"},
                {"AttributeName": "ts", "AttributeType": "N"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        ddb.create_table(
            TableName="test-pricing",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield
        dynamo._RESOURCE = None


@pytest.fixture
def register_account():
    from common import dynamo
    from common.models import Account

    def _register(regions=None):
        account = Account(
            account_id=ACCOUNT_ID,
            name="sandbox",
            external_id="test-external-id",
            regions=regions or [REGION],
        )
        dynamo.put_account(account)
        return account

    return _register


@pytest.fixture
def ec2():
    return boto3.client("ec2", region_name=REGION)


@pytest.fixture
def make_volume(ec2):
    def _make(size=100, vtype="gp3", tags=None, attach=False):
        kwargs = {"AvailabilityZone": f"{REGION}a", "Size": size, "VolumeType": vtype}
        if tags:
            kwargs["TagSpecifications"] = [
                {
                    "ResourceType": "volume",
                    "Tags": [{"Key": k, "Value": v} for k, v in tags.items()],
                }
            ]
        volume_id = ec2.create_volume(**kwargs)["VolumeId"]
        if attach:
            inst = ec2.run_instances(ImageId="ami-12345678", MinCount=1, MaxCount=1)
            iid = inst["Instances"][0]["InstanceId"]
            ec2.attach_volume(VolumeId=volume_id, InstanceId=iid, Device="/dev/sdf")
        return volume_id

    return _make
