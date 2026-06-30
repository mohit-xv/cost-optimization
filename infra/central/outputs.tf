output "api_invoke_url" {
  description = "Base URL for the REST API (set as the frontend's NEXT_PUBLIC_API_BASE_URL)."
  value       = aws_api_gateway_stage.stage.invoke_url
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.pool.id
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "cognito_domain" {
  value = "${aws_cognito_user_pool_domain.domain.domain}.auth.${var.region}.amazoncognito.com"
}

output "region" {
  value = var.region
}

output "lambda_exec_role_arn" {
  description = "Lock target-account role trust to this ARN (central_principal_arns) for tightest security."
  value       = aws_iam_role.lambda_exec.arn
}
