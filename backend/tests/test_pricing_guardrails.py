"""Unit tests for cost attribution and safety guardrails."""
from common import pricing
from common.guardrails import is_protected


def test_ebs_burn_us_east_1():
    assert pricing.ebs_monthly_burn(100, "gp3", "us-east-1") == 8.0
    assert pricing.ebs_monthly_burn(100, "gp2", "us-east-1") == 10.0


def test_ebs_burn_region_multiplier():
    # Tokyo gp3 fallback rate = 0.08 * 1.20 = 0.096 -> 100 GB = 9.6
    assert round(pricing.ebs_monthly_burn(100, "gp3", "ap-northeast-1"), 2) == 9.6


def test_gp3_provisioned_iops_surcharge():
    # 100 GB gp3 (8.0) + 1000 IOPS over the 3000 baseline * 0.005
    assert pricing.ebs_monthly_burn(100, "gp3", "us-east-1", iops=4000) == 8.0 + 1000 * 0.005


def test_guardrail_protected():
    assert is_protected({"CostKiller:Protect": "true"})[0] is True
    assert is_protected({"DoNotDelete": ""})[0] is True
    assert is_protected({"Environment": "production"})[0] is True
    assert is_protected({"aws:autoscaling:groupName": "asg-1"})[0] is True


def test_guardrail_not_protected():
    assert is_protected({"Name": "scratch"})[0] is False
    assert is_protected({"CostKiller:Protect": "false"})[0] is False
    assert is_protected({"Environment": "dev"})[0] is False
    assert is_protected([])[0] is False


def test_guardrail_accepts_ec2_tag_list():
    tags = [{"Key": "Environment", "Value": "prod"}]
    protected, reason = is_protected(tags)
    assert protected is True
    assert reason.startswith("protected_environment")
