"""Tiny helpers for API Gateway (proxy integration) Lambda responses."""
from __future__ import annotations

import json

_CORS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
}


def response(status: int, body) -> dict:
    return {"statusCode": status, "headers": _CORS, "body": json.dumps(body)}


def parse_body(event: dict) -> dict:
    body = event.get("body")
    if isinstance(body, str):
        return json.loads(body or "{}")
    return body or {}


def actor_from_event(event: dict, fallback: str = "unknown") -> str:
    """Identity of the caller, taken from the API Gateway Cognito authorizer claims."""
    claims = (
        ((event.get("requestContext") or {}).get("authorizer") or {}).get("claims") or {}
    )
    return claims.get("email") or claims.get("cognito:username") or fallback
