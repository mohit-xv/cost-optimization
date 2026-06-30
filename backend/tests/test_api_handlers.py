"""API Gateway proxy handler tests (event shape in / response shape out)."""
import json

from accounts import handler as accounts_handler
from common import dynamo
from execute import handler as execute_handler
from findings import handler as findings_handler
from scan.handler import run_scan


def test_accounts_crud():
    create = {
        "httpMethod": "POST",
        "body": json.dumps(
            {
                "accountId": "123456789012",
                "name": "sandbox",
                "externalId": "x",
                "regions": ["us-east-1"],
            }
        ),
    }
    assert accounts_handler.handler(create, None)["statusCode"] == 200

    listed = accounts_handler.handler({"httpMethod": "GET"}, None)
    body = json.loads(listed["body"])
    assert len(body["accounts"]) == 1
    assert body["accounts"][0]["accountId"] == "123456789012"

    deleted = accounts_handler.handler(
        {"httpMethod": "DELETE", "pathParameters": {"id": "123456789012"}}, None
    )
    assert deleted["statusCode"] == 200


def test_findings_list_summary_and_approve(register_account, make_volume):
    register_account()
    make_volume(size=50, vtype="gp3")  # 50 * 0.08 = 4.0
    run_scan()

    listed = findings_handler.handler(
        {"httpMethod": "GET", "queryStringParameters": None}, None
    )
    body = json.loads(listed["body"])
    assert body["summary"]["totalFlagged"] == 1
    assert body["summary"]["totalMonthlyWaste"] == 4.0
    assert body["summary"]["activeAccounts"] == 1

    finding_id = body["findings"][0]["findingId"]
    approve_event = {
        "httpMethod": "POST",
        "path": f"/findings/{finding_id}/approve",
        "pathParameters": {"id": finding_id},
    }
    assert findings_handler.handler(approve_event, None)["statusCode"] == 200
    # second approve -> 409 conflict (no longer PENDING_APPROVAL)
    assert findings_handler.handler(approve_event, None)["statusCode"] == 409


def test_execute_handler_dry_run(register_account, make_volume):
    register_account()
    make_volume()
    run_scan()
    finding_id = dynamo.list_findings()[0].finding_id
    dynamo.transition_status(finding_id, "PENDING_APPROVAL", "APPROVED")

    event = {"body": json.dumps({"findingIds": [finding_id], "dryRun": True})}
    resp = execute_handler.handler(event, None)
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 200
    assert body["results"][0]["status"] == "DRY_RUN_OK"
