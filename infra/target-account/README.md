# Target-account module

Deploys the two cross-account roles into a **target** (or sandbox) account so the central
Cost Killer account can scan it (read-only) and, after human approval, delete approved
resources.

- `CostKillerScanRole` — read-only (Cost Explorer, CloudWatch, EC2/ELB/RDS Describe).
- `CostKillerExecRole` — destructive actions, with **explicit Deny** on Auto Scaling
  Group managed resources, `Environment=prod/production`, and protective tags. IAM
  evaluates Deny before Allow, so this is a hard guardrail independent of app logic.

Both roles trust only the central account **and** require the shared `external_id`
(confused-deputy guard).

```bash
cp terraform.tfvars.example terraform.tfvars   # edit values
terraform init
terraform apply
```

Register the two output role ARNs + the same `external_id` in the central account
(Accounts page, or `POST /accounts`).
