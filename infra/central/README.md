# Central control plane

Deploys the Cost Killer control plane into the **primary** account: Cognito user pool +
Hosted UI, REST API Gateway with a Cognito authorizer, the five Python Lambdas, the four
DynamoDB tables, and the EventBridge schedule for periodic Discovery.

```bash
cp terraform.tfvars.example terraform.tfvars   # edit values
terraform init
terraform apply
```

After apply, wire the outputs into the frontend's `.env.local`:

| Output                 | Frontend env var                  |
| ---------------------- | --------------------------------- |
| `api_invoke_url`       | `NEXT_PUBLIC_API_BASE_URL`        |
| `cognito_user_pool_id` | `NEXT_PUBLIC_COGNITO_USER_POOL_ID`|
| `cognito_client_id`    | `NEXT_PUBLIC_COGNITO_CLIENT_ID`   |
| `cognito_domain`       | `NEXT_PUBLIC_COGNITO_DOMAIN`      |

Notes:
- The Lambda zip is built from `../../backend/src` by the `archive_file` data source, so
  run `terraform apply` from a checkout that includes `backend/`.
- `pandas` comes from the managed `AWSSDKPandas-Python311` layer — confirm the current
  layer version for your region (the default in `variables.tf` may be stale).
- Operators are invited via the Cognito console (self-signup is disabled).
- The `scan` Lambda is also invokable on a schedule (EventBridge) and on demand (`POST /scan`).
