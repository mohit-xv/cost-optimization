variable "central_account_id" {
  type        = string
  description = "AWS account ID of the central Cost Killer (primary) account that will assume these roles."
}

variable "central_principal_arns" {
  type        = list(string)
  description = "Principals in the central account allowed to assume these roles. Defaults to the central account's Lambda execution role; falls back to the account root."
  default     = []
}

variable "external_id" {
  type        = string
  description = "Shared secret required on AssumeRole (confused-deputy guard). Use a long random UUID, identical to the central deployment's EXTERNAL_ID."
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

variable "protected_environments" {
  type        = list(string)
  description = "Values of the Environment tag that must never be deleted."
  default     = ["prod", "production"]
}

variable "protected_tag_keys" {
  type        = list(string)
  description = "Tag keys whose presence (value 'true') protects a resource from deletion."
  default     = ["CostKiller:Protect", "DoNotDelete"]
}

variable "tags" {
  type    = map(string)
  default = {}
}
