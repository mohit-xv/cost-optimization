// In-memory mock API for local development when NEXT_PUBLIC_API_BASE_URL is unset.
// Lets you click through scan -> approve -> execute without a deployed backend.
import type {
  Account,
  ExecutionResponse,
  Finding,
  FindingsResponse,
  FindingsSummary,
} from "@/lib/types";

let nextSnap = 1000;

function seed(): Finding[] {
  const now = Math.floor(Date.now() / 1000);
  const mk = (
    resourceId: string,
    resourceType: string,
    region: string,
    daysIdle: number,
    monthlyBurn: number,
    metadata: Record<string, unknown>
  ): Finding => ({
    findingId: `123456789012#${region}#${resourceId}`,
    accountId: "123456789012",
    region,
    resourceId,
    resourceType,
    status: "PENDING_APPROVAL",
    daysIdle,
    monthlyBurn,
    dailyBurn: Math.round((monthlyBurn / 30) * 100) / 100,
    metadata,
    scanId: "demo-scan",
    updatedAt: now,
  });

  return [
    mk("vol-0a1b2c3d4e5f60001", "EBS_VOLUME", "us-east-1", 41, 40.0, { sizeGb: 500, volumeType: "gp3" }),
    mk("vol-0f9e8d7c6b5a40002", "EBS_VOLUME", "us-east-1", 18, 8.0, { sizeGb: 100, volumeType: "gp3" }),
    mk("eipalloc-0abc123def0003", "ELASTIC_IP", "us-east-1", 30, 3.6, { publicIp: "52.10.20.30" }),
    mk("nat-0aa11bb22cc330004", "NAT_GATEWAY", "eu-west-1", 14, 35.4, { bytesProcessed: 0 }),
    mk("vol-0123456789abc0005", "EBS_VOLUME", "eu-west-1", 63, 5.04, { sizeGb: 50, volumeType: "gp2" }),
  ];
}

let _findings: Finding[] = seed();
let _accounts: Account[] = [
  {
    accountId: "123456789012",
    name: "sandbox (demo)",
    externalId: "demo-external-id",
    regions: ["us-east-1", "eu-west-1"],
    scanRoleArn: null,
    execRoleArn: null,
    enabled: true,
  },
];

function summary(): FindingsSummary {
  const totalMonthlyWaste =
    Math.round(_findings.reduce((s, f) => s + f.monthlyBurn, 0) * 100) / 100;
  const accounts = Array.from(new Set(_findings.map((f) => f.accountId)));
  return {
    totalMonthlyWaste,
    totalFlagged: _findings.length,
    activeAccounts: accounts.length,
    accounts,
  };
}

function setStatus(id: string, from: string, to: Finding["status"]): boolean {
  const f = _findings.find((x) => x.findingId === id);
  if (!f || f.status !== from) return false;
  f.status = to;
  return true;
}

export const mockApi = {
  listFindings: async (_params?: { status?: string; accountId?: string }): Promise<FindingsResponse> => ({
    findings: _findings.map((f) => ({ ...f })),
    summary: summary(),
  }),
  approve: async (id: string) => ({ updated: setStatus(id, "PENDING_APPROVAL", "APPROVED") }),
  ignore: async (id: string) => ({ updated: setStatus(id, "PENDING_APPROVAL", "IGNORED") }),
  runScan: async (): Promise<unknown> => {
    _findings = seed();
    return { flagged: _findings.length };
  },
  execute: async (findingIds: string[], dryRun: boolean): Promise<ExecutionResponse> => {
    const results = findingIds.map((id) => {
      const f = _findings.find((x) => x.findingId === id);
      if (!f || f.status !== "APPROVED") {
        return { findingId: id, status: "SKIPPED", reason: "not approved" };
      }
      if (dryRun) return { findingId: id, status: "DRY_RUN_OK", reason: "dry_run_ok" };
      f.status = "DELETED";
      return {
        findingId: id,
        status: "DELETED",
        snapshotId: `snap-demo${nextSnap++}`,
        receipt: `demo-receipt-${id.slice(-8)}`,
      };
    });
    return {
      results,
      deleted: results.filter((r) => r.status === "DELETED").length,
      requested: findingIds.length,
    };
  },
  listAccounts: async (): Promise<{ accounts: Account[] }> => ({
    accounts: _accounts.map((a) => ({ ...a })),
  }),
  upsertAccount: async (account: Partial<Account>): Promise<Account> => {
    const next: Account = {
      accountId: String(account.accountId),
      name: account.name ?? "",
      externalId: account.externalId ?? "",
      regions: account.regions ?? [],
      scanRoleArn: account.scanRoleArn ?? null,
      execRoleArn: account.execRoleArn ?? null,
      enabled: account.enabled ?? true,
    };
    _accounts = [..._accounts.filter((a) => a.accountId !== next.accountId), next];
    return next;
  },
  deleteAccount: async (id: string) => {
    _accounts = _accounts.filter((a) => a.accountId !== id);
    return { deleted: true };
  },
};
