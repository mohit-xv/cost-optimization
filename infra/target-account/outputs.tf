output "scan_role_arn" {
  description = "ARN of the read-only Scan role. Register this in the central account's Accounts table."
  value       = aws_iam_role.scan.arn
}

output "exec_role_arn" {
  description = "ARN of the high-privilege Exec role. Register this in the central account's Accounts table."
  value       = aws_iam_role.exec.arn
}
