"""Weekly pricing refresh Lambda.

Polls the AWS Price List API (``GetProducts``) for EBS GB-month rates per region and
volume type, and caches them in the PricingMatrix DynamoDB table. Discovery reads from
that cache so it never makes synchronous Price List / Cost Explorer calls during a scan.

The Price List API is only available in ``us-east-1`` and ``ap-south-1``.
"""
from __future__ import annotations

import json

import boto3

from common import dynamo, pricing

# Region code -> Price List "location" attribute value.
_REGION_LOCATION = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-1": "US West (N. California)",
    "us-west-2": "US West (Oregon)",
    "eu-west-1": "EU (Ireland)",
    "eu-central-1": "EU (Frankfurt)",
    "ap-south-1": "Asia Pacific (Mumbai)",
    "ap-northeast-1": "Asia Pacific (Tokyo)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-southeast-2": "Asia Pacific (Sydney)",
    "sa-east-1": "South America (Sao Paulo)",
}

_VOLUME_TYPES = ["gp3", "gp2", "io1", "io2", "st1", "sc1", "standard"]


def _pricing_client():
    return boto3.client("pricing", region_name="us-east-1")


def _fetch_ebs_gb_month(client, location: str, volume_api_name: str):
    resp = client.get_products(
        ServiceCode="AmazonEC2",
        Filters=[
            {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "Storage"},
            {"Type": "TERM_MATCH", "Field": "volumeApiName", "Value": volume_api_name},
            {"Type": "TERM_MATCH", "Field": "location", "Value": location},
        ],
        MaxResults=1,
    )
    for raw in resp.get("PriceList", []):
        product = json.loads(raw) if isinstance(raw, str) else raw
        for term in product.get("terms", {}).get("OnDemand", {}).values():
            for dim in term.get("priceDimensions", {}).values():
                usd = dim.get("pricePerUnit", {}).get("USD")
                if usd is not None:
                    return float(usd)
    return None


def refresh(regions=None) -> dict:
    client = _pricing_client()
    regions = regions or list(_REGION_LOCATION.keys())
    written = 0
    for region in regions:
        location = _REGION_LOCATION.get(region)
        if not location:
            continue
        for vtype in _VOLUME_TYPES:
            try:
                rate = _fetch_ebs_gb_month(client, location, vtype)
            except Exception as exc:  # best-effort; pricing.py has fallback list prices
                print(f"pricing fetch failed {region}/{vtype}: {exc}")
                continue
            if rate is None:
                continue
            dynamo.put_pricing_item(
                {
                    "pk": pricing.ebs_pricing_pk(region, vtype),
                    "service": "EBS",
                    "region": region,
                    "volumeType": vtype,
                    "gbMonth": rate,
                }
            )
            written += 1
    return {"written": written, "regions": len(regions)}


def handler(event, context):
    regions = (event or {}).get("regions")
    return refresh(regions)
