"""(De)serialization helpers for DynamoDB.

DynamoDB's document client stores numbers as ``Decimal`` and rejects native ``float``.
These helpers convert recursively between Python-native values and DynamoDB-safe values.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any


def to_dynamo(obj: Any) -> Any:
    """Recursively convert floats to Decimal so the value is safe to put in DynamoDB."""
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: to_dynamo(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_dynamo(v) for v in obj]
    return obj


def from_dynamo(obj: Any) -> Any:
    """Recursively convert DynamoDB Decimals back to int/float for JSON serialization."""
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, dict):
        return {k: from_dynamo(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [from_dynamo(v) for v in obj]
    return obj
