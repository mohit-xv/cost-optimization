resource "aws_dynamodb_table" "findings" {
  name         = "${local.name}-Findings"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "findingId"

  attribute {
    name = "findingId"
    type = "S"
  }
  attribute {
    name = "status"
    type = "S"
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    projection_type = "ALL"
  }

  tags = var.tags
}

resource "aws_dynamodb_table" "accounts" {
  name         = "${local.name}-Accounts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "accountId"

  attribute {
    name = "accountId"
    type = "S"
  }

  tags = var.tags
}

resource "aws_dynamodb_table" "execution_log" {
  name         = "${local.name}-ExecutionLog"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "findingId"
  range_key    = "ts"

  attribute {
    name = "findingId"
    type = "S"
  }
  attribute {
    name = "ts"
    type = "N"
  }

  tags = var.tags
}

resource "aws_dynamodb_table" "pricing" {
  name         = "${local.name}-PricingMatrix"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  tags = var.tags
}
