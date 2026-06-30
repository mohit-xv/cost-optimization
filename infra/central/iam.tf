data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_exec" {
  name               = "${local.name}-lambda-exec"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "lambda_policy" {
  statement {
    sid       = "Logs"
    effect    = "Allow"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:*"]
  }

  statement {
    sid    = "DynamoDB"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan",
    ]
    resources = [
      aws_dynamodb_table.findings.arn,
      "${aws_dynamodb_table.findings.arn}/index/*",
      aws_dynamodb_table.accounts.arn,
      aws_dynamodb_table.execution_log.arn,
      aws_dynamodb_table.pricing.arn,
    ]
  }

  # Assume the cross-account Scan/Exec roles by name in ANY target account.
  statement {
    sid       = "AssumeTargetRoles"
    effect    = "Allow"
    actions   = ["sts:AssumeRole"]
    resources = [
      "arn:aws:iam::*:role/${var.scan_role_name}",
      "arn:aws:iam::*:role/${var.exec_role_name}",
    ]
  }

  # Central-account use: Price List (pricing Lambda) + Cost Explorer + CloudWatch.
  statement {
    sid    = "CostAndPricing"
    effect = "Allow"
    actions = [
      "pricing:GetProducts",
      "ce:GetCostAndUsage",
      "ce:GetCostAndUsageWithResources",
      "ce:GetRightsizingRecommendation",
      "cloudwatch:GetMetricData",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "lambda_policy" {
  name   = "${local.name}-lambda-policy"
  role   = aws_iam_role.lambda_exec.id
  policy = data.aws_iam_policy_document.lambda_policy.json
}
