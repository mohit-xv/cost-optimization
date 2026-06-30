"""Deterministic cost attribution from the cached Price List matrix.

The weekly ``pricing`` Lambda populates the PricingMatrix DynamoDB table from the AWS
Price List API. Discovery reads rates from that table; if a rate is missing we fall back
to a built-in list-price table so the platform still produces sensible numbers before the
pricing Lambda has run.
"""
from __future__ import annotations

from common import dynamo

# USD per GB-month, us-east-1 list prices (fallback only).
_EBS_GB_MONTH_FALLBACK = {
    "gp3": 0.08,
    "gp2": 0.10,
    "io1": 0.125,
    "io2": 0.125,
    "st1": 0.045,
    "sc1": 0.015,
    "standard": 0.05,
}

# Coarse per-region multipliers vs us-east-1 (fallback only; real data comes from the
# Price List Lambda which stores exact per-region rates).
_REGION_MULTIPLIER = {
    "us-east-1": 1.00,
    "us-east-2": 1.00,
    "us-west-2": 1.00,
    "eu-west-1": 1.05,
    "ap-northeast-1": 1.20,
    "sa-east-1": 1.40,
}

_GP3_BASELINE_IOPS = 3000
_GP3_IOPS_MONTH = 0.005       # per provisioned IOPS-month over baseline (us-east-1)
_IO_IOPS_MONTH = 0.065        # io1/io2 per provisioned IOPS-month (us-east-1)

HOURS_PER_MONTH = 730

# Public IPv4 / Elastic IP: since 2024-02-01 every public IPv4 is billed $0.005/hr.
_EIP_HOURLY = 0.005

# NAT Gateway hourly uptime rate per region (fallback; data-processing fees excluded
# because an idle gateway processes ~0 GB).
_NAT_HOURLY = {
    "us-east-1": 0.045,
    "us-east-2": 0.045,
    "us-west-2": 0.045,
    "eu-west-1": 0.048,
    "ap-northeast-1": 0.062,
    "ap-south-1": 0.056,
    "sa-east-1": 0.093,
}


def ebs_pricing_pk(region: str, volume_type: str) -> str:
    return f"EBS#{region}#{volume_type}"


def ebs_gb_month_rate(region: str, volume_type: str) -> float:
    item = dynamo.get_pricing_item(ebs_pricing_pk(region, volume_type))
    if item and "gbMonth" in item:
        return float(item["gbMonth"])
    base = _EBS_GB_MONTH_FALLBACK.get(volume_type, _EBS_GB_MONTH_FALLBACK["gp3"])
    return base * _REGION_MULTIPLIER.get(region, 1.0)


def ebs_monthly_burn(size_gb: float, volume_type: str, region: str, iops: int = 0) -> float:
    """Estimated monthly cost of an EBS volume (storage + provisioned IOPS)."""
    burn = float(size_gb) * ebs_gb_month_rate(region, volume_type)
    if volume_type in ("io1", "io2") and iops:
        burn += iops * _IO_IOPS_MONTH
    elif volume_type == "gp3" and iops and iops > _GP3_BASELINE_IOPS:
        burn += (iops - _GP3_BASELINE_IOPS) * _GP3_IOPS_MONTH
    return round(burn, 4)


def eip_monthly_burn() -> float:
    """Monthly cost of an idle (or any) public IPv4 / Elastic IP."""
    return round(_EIP_HOURLY * HOURS_PER_MONTH, 4)


def nat_gateway_monthly_burn(region: str) -> float:
    """Monthly uptime cost of a NAT Gateway (data-processing excluded for an idle one)."""
    hourly = _NAT_HOURLY.get(region, 0.045)
    return round(hourly * HOURS_PER_MONTH, 4)
