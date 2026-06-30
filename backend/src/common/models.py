"""Domain models and the Findings state machine."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional

from common.serde import from_dynamo, to_dynamo


class FindingStatus(str, Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    DELETING = "DELETING"
    DELETED = "DELETED"
    IGNORED = "IGNORED"
    FAILED = "FAILED"


# Statuses a re-scan must NOT overwrite back to PENDING_APPROVAL.
PROTECTED_FROM_RESCAN = {
    FindingStatus.APPROVED.value,
    FindingStatus.DELETING.value,
    FindingStatus.DELETED.value,
    FindingStatus.IGNORED.value,
}


class ResourceType(str, Enum):
    EBS_VOLUME = "EBS_VOLUME"
    ELASTIC_IP = "ELASTIC_IP"          # phase 2
    NAT_GATEWAY = "NAT_GATEWAY"        # phase 2
    EBS_SNAPSHOT = "EBS_SNAPSHOT"      # phase 2
    LOAD_BALANCER = "LOAD_BALANCER"    # phase 3
    EC2_INSTANCE = "EC2_INSTANCE"      # phase 3
    RDS_INSTANCE = "RDS_INSTANCE"      # phase 4


def make_finding_id(account_id: str, region: str, resource_id: str) -> str:
    """Stable, idempotent key for a flagged resource."""
    return f"{account_id}#{region}#{resource_id}"


@dataclass
class Finding:
    finding_id: str
    account_id: str
    region: str
    resource_id: str
    resource_type: str
    status: str = FindingStatus.PENDING_APPROVAL.value
    days_idle: int = 0
    monthly_burn: float = 0.0
    daily_burn: float = 0.0
    metadata: dict = field(default_factory=dict)
    scan_id: Optional[str] = None
    updated_at: int = field(default_factory=lambda: int(time.time()))

    def to_item(self) -> dict:
        return {
            "findingId": self.finding_id,
            "accountId": self.account_id,
            "region": self.region,
            "resourceId": self.resource_id,
            "resourceType": self.resource_type,
            "status": self.status,
            "daysIdle": int(self.days_idle),
            "monthlyBurn": Decimal(str(round(self.monthly_burn, 4))),
            "dailyBurn": Decimal(str(round(self.daily_burn, 4))),
            "metadata": to_dynamo(self.metadata),
            "scanId": self.scan_id,
            "updatedAt": int(self.updated_at),
        }

    def to_json(self) -> dict:
        """Plain JSON-serializable dict for API responses."""
        return {
            "findingId": self.finding_id,
            "accountId": self.account_id,
            "region": self.region,
            "resourceId": self.resource_id,
            "resourceType": self.resource_type,
            "status": self.status,
            "daysIdle": int(self.days_idle),
            "monthlyBurn": round(self.monthly_burn, 4),
            "dailyBurn": round(self.daily_burn, 4),
            "metadata": self.metadata,
            "scanId": self.scan_id,
            "updatedAt": int(self.updated_at),
        }

    @staticmethod
    def from_item(item: dict) -> "Finding":
        return Finding(
            finding_id=item["findingId"],
            account_id=item["accountId"],
            region=item["region"],
            resource_id=item["resourceId"],
            resource_type=item["resourceType"],
            status=item["status"],
            days_idle=int(item.get("daysIdle", 0)),
            monthly_burn=float(item.get("monthlyBurn", 0)),
            daily_burn=float(item.get("dailyBurn", 0)),
            metadata=from_dynamo(item.get("metadata", {})),
            scan_id=item.get("scanId"),
            updated_at=int(item.get("updatedAt", 0)),
        )


@dataclass
class Account:
    account_id: str
    name: str
    external_id: str
    regions: list[str] = field(default_factory=list)
    scan_role_arn: Optional[str] = None
    exec_role_arn: Optional[str] = None
    enabled: bool = True

    def to_item(self) -> dict:
        return {
            "accountId": self.account_id,
            "name": self.name,
            "externalId": self.external_id,
            "regions": self.regions,
            "scanRoleArn": self.scan_role_arn,
            "execRoleArn": self.exec_role_arn,
            "enabled": self.enabled,
        }

    def to_json(self) -> dict:
        return self.to_item()

    @staticmethod
    def from_item(item: dict) -> "Account":
        return Account(
            account_id=item["accountId"],
            name=item.get("name", ""),
            external_id=item.get("externalId", ""),
            regions=list(item.get("regions", [])),
            scan_role_arn=item.get("scanRoleArn"),
            exec_role_arn=item.get("execRoleArn"),
            enabled=bool(item.get("enabled", True)),
        )
