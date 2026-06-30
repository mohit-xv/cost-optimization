locals {
  functions = {
    findings = { handler = "findings.handler.handler", timeout = 30, memory = 256, layers = [] }
    accounts = { handler = "accounts.handler.handler", timeout = 30, memory = 256, layers = [] }
    scan     = { handler = "scan.handler.handler", timeout = 300, memory = var.scan_memory_mb, layers = [var.pandas_layer_arn] }
    execute  = { handler = "execute.handler.handler", timeout = 300, memory = var.execute_memory_mb, layers = [] }
    pricing  = { handler = "pricing.handler.handler", timeout = 120, memory = 256, layers = [] }
  }
}

resource "aws_cloudwatch_log_group" "fn" {
  for_each          = local.functions
  name              = "/aws/lambda/${local.name}-${each.key}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_lambda_function" "fn" {
  for_each = local.functions

  function_name    = "${local.name}-${each.key}"
  role             = aws_iam_role.lambda_exec.arn
  runtime          = "python3.11"
  handler          = each.value.handler
  filename         = data.archive_file.lambda_src.output_path
  source_code_hash = data.archive_file.lambda_src.output_base64sha256
  timeout          = each.value.timeout
  memory_size      = each.value.memory
  layers           = each.value.layers

  environment {
    variables = local.common_env
  }

  tags       = var.tags
  depends_on = [aws_cloudwatch_log_group.fn]
}

# --- Scheduled Discovery (EventBridge -> scan Lambda) ----------------------------
resource "aws_cloudwatch_event_rule" "scan_schedule" {
  name                = "${local.name}-scan-schedule"
  schedule_expression = var.scan_schedule_expression
  tags                = var.tags
}

resource "aws_cloudwatch_event_target" "scan" {
  rule = aws_cloudwatch_event_rule.scan_schedule.name
  arn  = aws_lambda_function.fn["scan"].arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeScan"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fn["scan"].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scan_schedule.arn
}
