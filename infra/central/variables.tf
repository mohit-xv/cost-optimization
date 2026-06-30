variable "region" {
  type    = string
  default = "us-east-1"
}

variable "project" {
  type    = string
  default = "cost-killer"
}

variable "external_id" {
  type        = string
  description = "Shared secret used on cross-account AssumeRole. Must match each target account's module."
  sensitive   = true
}

variable "scan_role_name" {
  type    = string
  default = "CostKillerScanRole"
}

variable "exec_role_name" {
  type    = string
  default = "CostKillerExecRole"
}

variable "idle_days_threshold" {
  type    = number
  default = 7
}

variable "default_regions" {
  type        = list(string)
  description = "Regions scanned when an account has none configured."
  default     = ["us-east-1"]
}

variable "pandas_layer_arn" {
  type        = string
  description = "ARN of the AWS-managed AWSSDKPandas-Python311 layer for this region. Find the current version in the AWS docs / console for your region."
  default     = "arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python311:20"
}

variable "scan_memory_mb" {
  type        = number
  description = "Discovery Lambda memory. Keep >= 2048 so the pandas layer cold-start stays well under the 29s API GW timeout."
  default     = 2048
}

variable "execute_memory_mb" {
  type    = number
  default = 1024
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "scan_schedule_expression" {
  type        = string
  description = "EventBridge schedule for periodic Discovery."
  default     = "cron(0 3 * * ? *)" # daily 03:00 UTC
}

variable "cognito_domain_prefix" {
  type        = string
  description = "Globally-unique prefix for the Cognito Hosted UI domain."
  default     = "cost-killer-auth"
}

variable "cognito_callback_urls" {
  type    = list(string)
  default = ["http://localhost:3000/api/auth/callback"]
}

variable "cognito_logout_urls" {
  type    = list(string)
  default = ["http://localhost:3000"]
}

variable "tags" {
  type    = map(string)
  default = { Project = "cost-killer" }
}
