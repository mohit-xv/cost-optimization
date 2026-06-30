terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

locals {
  # If no explicit principals are given, trust the central account root (still gated by ExternalId).
  trusted_principals = length(var.central_principal_arns) > 0 ? var.central_principal_arns : [
    "arn:aws:iam::${var.central_account_id}:root"
  ]

  # Destructive actions the Exec role is allowed to perform (MVP: EBS; rest are for expansion).
  destructive_actions = [
    "ec2:DeleteVolume",
    "ec2:DeleteSnapshot",
    "ec2:ReleaseAddress",
    "ec2:DeleteNatGateway",
    "ec2:TerminateInstances",
    "ec2:StopInstances",
    "ec2:DeleteNetworkInterface",
    "ec2:DeregisterImage",
    "elasticloadbalancing:DeleteLoadBalancer",
    "rds:DeleteDBInstance",
  ]
}

# ---------------------------------------------------------------------------------
# Trust policy shared by both roles: only the central account, only with the ExternalId.
# ---------------------------------------------------------------------------------
data "aws_iam_policy_document" "assume_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = local.trusted_principals
    }

    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.external_id]
    }
  }
}

# =================================================================================
# 1) Scan role — READ ONLY. Discovery assumes this; it can never mutate anything.
# =================================================================================
resource "aws_iam_role" "scan" {
  name                 = var.scan_role_name
  assume_role_policy   = data.aws_iam_policy_document.assume_trust.json
  max_session_duration = 3600
  tags                 = var.tags
}

data "aws_iam_policy_document" "scan_readonly" {
  statement {
    sid    = "ReadOnlyDiscovery"
    effect = "Allow"
    actions = [
      "ce:GetCostAndUsage",
      "ce:GetCostAndUsageWithResources",
      "ce:GetRightsizingRecommendation",
      "cloudwatch:GetMetricData",
      "cloudwatch:ListMetrics",
      "cloudtrail:LookupEvents",
      "ec2:Describe*",
      "elasticloadbalancing:Describe*",
      "rds:Describe*",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "scan_readonly" {
  name   = "CostKillerScanReadOnly"
  role   = aws_iam_role.scan.id
  policy = data.aws_iam_policy_document.scan_readonly.json
}

# =================================================================================
# 2) Exec role — high privilege, tightly guarded. Execution assumes this.
#    Explicit Deny statements are evaluated BEFORE Allow, so even a buggy Lambda
#    cannot delete an ASG-managed or production-/protect-tagged resource.
# =================================================================================
resource "aws_iam_role" "exec" {
  name                 = var.exec_role_name
  assume_role_policy   = data.aws_iam_policy_document.assume_trust.json
  max_session_duration = 3600
  tags                 = var.tags
}

data "aws_iam_policy_document" "exec_policy" {
  # Allow: read for re-verification + snapshot-before-delete + the destructive actions.
  statement {
    sid    = "AllowReadAndSnapshot"
    effect = "Allow"
    actions = [
      "ec2:Describe*",
      "ec2:CreateSnapshot",
      "ec2:CreateTags",
      "elasticloadbalancing:Describe*",
      "rds:Describe*",
      "rds:CreateDBSnapshot",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "AllowDestructiveActions"
    effect    = "Allow"
    actions   = local.destructive_actions
    resources = ["*"]
  }

  # Deny: Auto Scaling Group managed resources.
  statement {
    sid       = "DenyAutoScalingManaged"
    effect    = "Deny"
    actions   = local.destructive_actions
    resources = ["*"]
    condition {
      test     = "Null"
      variable = "aws:ResourceTag/aws:autoscaling:groupName"
      values   = ["false"] # tag IS present -> deny
    }
  }

  # Deny: production Environment tag.
  statement {
    sid       = "DenyProductionEnvironment"
    effect    = "Deny"
    actions   = local.destructive_actions
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Environment"
      values   = var.protected_environments
    }
  }

  # Deny: explicit protective tags set to "true".
  dynamic "statement" {
    for_each = var.protected_tag_keys
    content {
      sid       = "DenyProtectTag${replace(replace(statement.value, ":", ""), "-", "")}"
      effect    = "Deny"
      actions   = local.destructive_actions
      resources = ["*"]
      condition {
        test     = "StringEquals"
        variable = "aws:ResourceTag/${statement.value}"
        values   = ["true"]
      }
    }
  }
}

resource "aws_iam_role_policy" "exec_policy" {
  name   = "CostKillerExecPolicy"
  role   = aws_iam_role.exec.id
  policy = data.aws_iam_policy_document.exec_policy.json
}
