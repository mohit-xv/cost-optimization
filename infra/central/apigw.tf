resource "aws_api_gateway_rest_api" "api" {
  name = "${local.name}-api"
  endpoint_configuration {
    types = ["REGIONAL"]
  }
  tags = var.tags
}

# JWTs from the Cognito user pool are validated HERE, at the edge — not in Next.js.
resource "aws_api_gateway_authorizer" "cognito" {
  name            = "cognito"
  rest_api_id     = aws_api_gateway_rest_api.api.id
  type            = "COGNITO_USER_POOLS"
  identity_source = "method.request.header.Authorization"
  provider_arns   = [aws_cognito_user_pool.pool.arn]
}

# --- Resources (paths) ------------------------------------------------------------
resource "aws_api_gateway_resource" "findings" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "findings"
}

resource "aws_api_gateway_resource" "findings_id" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.findings.id
  path_part   = "{id}"
}

resource "aws_api_gateway_resource" "findings_approve" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.findings_id.id
  path_part   = "approve"
}

resource "aws_api_gateway_resource" "findings_ignore" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.findings_id.id
  path_part   = "ignore"
}

resource "aws_api_gateway_resource" "accounts" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "accounts"
}

resource "aws_api_gateway_resource" "accounts_id" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.accounts.id
  path_part   = "{id}"
}

resource "aws_api_gateway_resource" "scan" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "scan"
}

resource "aws_api_gateway_resource" "execute" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "execute"
}

locals {
  routes = {
    findings_list    = { resource_id = aws_api_gateway_resource.findings.id, method = "GET", fn = "findings" }
    findings_approve = { resource_id = aws_api_gateway_resource.findings_approve.id, method = "POST", fn = "findings" }
    findings_ignore  = { resource_id = aws_api_gateway_resource.findings_ignore.id, method = "POST", fn = "findings" }
    accounts_list    = { resource_id = aws_api_gateway_resource.accounts.id, method = "GET", fn = "accounts" }
    accounts_create  = { resource_id = aws_api_gateway_resource.accounts.id, method = "POST", fn = "accounts" }
    accounts_delete  = { resource_id = aws_api_gateway_resource.accounts_id.id, method = "DELETE", fn = "accounts" }
    scan_run         = { resource_id = aws_api_gateway_resource.scan.id, method = "POST", fn = "scan" }
    execute_run      = { resource_id = aws_api_gateway_resource.execute.id, method = "POST", fn = "execute" }
  }

  cors_resources = {
    findings         = aws_api_gateway_resource.findings.id
    findings_approve = aws_api_gateway_resource.findings_approve.id
    findings_ignore  = aws_api_gateway_resource.findings_ignore.id
    accounts         = aws_api_gateway_resource.accounts.id
    accounts_id      = aws_api_gateway_resource.accounts_id.id
    scan             = aws_api_gateway_resource.scan.id
    execute          = aws_api_gateway_resource.execute.id
  }
}

# --- Authorized methods + Lambda proxy integrations -------------------------------
resource "aws_api_gateway_method" "m" {
  for_each      = local.routes
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = each.value.resource_id
  http_method   = each.value.method
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "i" {
  for_each                = local.routes
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = each.value.resource_id
  http_method             = aws_api_gateway_method.m[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.fn[each.value.fn].invoke_arn
}

resource "aws_lambda_permission" "apigw" {
  for_each      = toset(["findings", "accounts", "scan", "execute"])
  statement_id  = "AllowAPIGateway-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fn[each.key].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}

# --- CORS preflight (OPTIONS) -----------------------------------------------------
resource "aws_api_gateway_method" "cors" {
  for_each      = local.cors_resources
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = each.value
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "cors" {
  for_each          = local.cors_resources
  rest_api_id       = aws_api_gateway_rest_api.api.id
  resource_id       = each.value
  http_method       = "OPTIONS"
  type              = "MOCK"
  request_templates = { "application/json" = "{\"statusCode\": 200}" }
}

resource "aws_api_gateway_method_response" "cors" {
  for_each    = local.cors_resources
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = each.value
  http_method = "OPTIONS"
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "cors" {
  for_each    = local.cors_resources
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = each.value
  http_method = "OPTIONS"
  status_code = aws_api_gateway_method_response.cors[each.key].status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
  depends_on = [aws_api_gateway_integration.cors]
}

# --- Deployment + stage -----------------------------------------------------------
resource "aws_api_gateway_deployment" "dep" {
  rest_api_id = aws_api_gateway_rest_api.api.id

  triggers = {
    redeploy = sha1(jsonencode([
      keys(local.routes),
      keys(local.cors_resources),
      aws_api_gateway_authorizer.cognito.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.i,
    aws_api_gateway_integration.cors,
  ]
}

resource "aws_api_gateway_stage" "stage" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  deployment_id = aws_api_gateway_deployment.dep.id
  stage_name    = "prod"
  tags          = var.tags
}
