data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Package the contents of backend/src so that common/, scan/, … sit at the zip root.
# Handlers are therefore addressed as "<package>.handler.handler".
data "archive_file" "lambda_src" {
  type        = "zip"
  source_dir  = "${path.module}/../../backend/src"
  output_path = "${path.module}/dist/lambda_src.zip"
}

locals {
  name = var.project

  common_env = {
    FINDINGS_TABLE      = aws_dynamodb_table.findings.name
    ACCOUNTS_TABLE      = aws_dynamodb_table.accounts.name
    EXECUTION_LOG_TABLE = aws_dynamodb_table.execution_log.name
    PRICING_TABLE       = aws_dynamodb_table.pricing.name
    SCAN_ROLE_NAME      = var.scan_role_name
    EXEC_ROLE_NAME      = var.exec_role_name
    EXTERNAL_ID         = var.external_id
    IDLE_DAYS_THRESHOLD = tostring(var.idle_days_threshold)
    DEFAULT_REGIONS     = join(",", var.default_regions)
  }
}
