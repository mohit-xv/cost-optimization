"""Cross-account STS AssumeRole helpers.

Every cross-account call goes through here so the ExternalId (confused-deputy guard) is
applied consistently for both the read-only Scan role and the high-privilege Exec role.
"""
from __future__ import annotations

import boto3

from common import config
from common.models import Account


def _role_name(role_arn: str | None, default_name: str) -> str:
    if role_arn:
        return role_arn.rstrip("/").split("/")[-1]
    return default_name


def assume_session(
    account_id: str,
    role_name: str,
    external_id: str,
    region: str | None = None,
    session_name: str = "cost-killer",
) -> boto3.Session:
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
    sts = boto3.client("sts")
    kwargs = {"RoleArn": role_arn, "RoleSessionName": session_name}
    if external_id:
        kwargs["ExternalId"] = external_id
    creds = sts.assume_role(**kwargs)["Credentials"]
    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        region_name=region,
    )


def scan_client(service: str, account: Account, region: str):
    """Client for read-only Discovery, assuming the target account's Scan role."""
    session = assume_session(
        account.account_id,
        _role_name(account.scan_role_arn, config.scan_role_name()),
        account.external_id or config.external_id(),
        region,
        session_name="cost-killer-scan",
    )
    return session.client(service, region_name=region)


def exec_client(service: str, account: Account, region: str):
    """Client for gated Execution, assuming the target account's high-privilege Exec role."""
    session = assume_session(
        account.account_id,
        _role_name(account.exec_role_arn, config.exec_role_name()),
        account.external_id or config.external_id(),
        region,
        session_name="cost-killer-exec",
    )
    return session.client(service, region_name=region)
