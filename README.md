# AWS Cost Killer — FinOps Automation Platform

A production-grade, web-based FinOps platform that scans single or multi-account AWS
environments, identifies idle / orphaned / over-provisioned resources, attributes real
cash burn, and lets a human **approve deletions in the UI** before anything is destroyed.

Two-phase, safety-first model:

1. **Discovery Mode** — read-only scan + cost attribution. Zero mutations.
2. **Permission-Gated Execution Mode** — deletes only what a human approved, behind
   Cognito auth, ExternalId-scoped STS roles, `DryRun`, TOCTOU re-verification and
   tag/ASG guardrails.

> **Implemented:** full architecture, with detection + execution for **unattached EBS
> volumes**, **unassociated Elastic IPs**, **idle NAT Gateways**, and **orphaned EBS
> snapshots**. Remaining resource types (ELB, EC2, RDS, ENI, AMI) are scaffolded for expansion.

## Repository layout

```
infra/
  central/          Terraform — control plane (Cognito, API GW, Lambdas, DynamoDB, S3)
  target-account/   Terraform — reusable module: ScanRole + ExecRole (ExternalId-gated)
backend/
  src/
    common/         shared: config, models, serde, dynamo, sts_assume, pricing, guardrails
    scan/           Discovery Lambda (EBS detection + pandas burn ranking)
    findings/       list / approve / ignore Lambda
    accounts/       target-account registry CRUD Lambda
    pricing/        weekly Price List -> PricingMatrix Lambda
    execute/        gated deletion Lambda (DryRun + TOCTOU + receipts)
  tests/            pytest + moto (mocked AWS) — full Discovery->Approve->Execute flow
frontend/           Next.js (App Router, TS, Tailwind) dashboard — deploy to Vercel
```

## Backend — local dev & test

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

Tests run entirely against **moto** (mocked AWS) — no real AWS calls, nothing is deleted.

### Lambda packaging

Each Lambda zips the **contents of `backend/src/`** (so `common/`, `scan/`, … are at the
zip root). Handlers are therefore addressed as `scan.handler.handler`,
`execute.handler.handler`, etc. `pandas` is provided by the AWS-managed
`AWSSDKPandas-Python311` layer (not bundled).

## Frontend — local dev

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build      # production build (also runs type-check)
```

Configure the API base URL and Cognito settings in `frontend/.env.local`
(see `.env.local.example`).

## Deploy (sandbox)

1. `cd infra/central && terraform init && terraform apply` — control plane in the primary account.
2. `cd infra/target-account && terraform init && terraform apply` — deploy the two
   cross-account roles into each target/sandbox account (pass the central account ID +
   ExternalId).
3. Register the sandbox account via the dashboard **Accounts** page (or `POST /accounts`).
4. Run **Discovery**, review findings, approve, then **Execute Approved Deletions**.

> Terraform is a deliverable here; install Terraform locally to `validate`/`plan`.

## Live smoke test (sandbox only)

Create a deliberate 5 GB unattached `gp3` volume, run Discovery, confirm it appears with
the correct monthly burn, approve it, and run Execute (DryRun preview first). Confirm a
volume tagged `CostKiller:Protect=true` is **never** flagged or deleted.

## Roadmap

- **Phase 2 (in progress):** ✅ unassociated Elastic IPs, ✅ idle NAT Gateways,
  ✅ orphaned EBS snapshots; remaining — enable **FOCUS 1.2 Data Exports** (S3) as the
  cost-attribution backbone.
- **Phase 3:** idle/unused load balancers, underutilized/stopped EC2 (rightsizing).
- **Phase 4:** idle RDS, orphaned ENIs, old AMIs.
