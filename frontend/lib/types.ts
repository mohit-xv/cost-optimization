export type FindingStatus =
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "DELETING"
  | "DELETED"
  | "IGNORED"
  | "FAILED";

export interface Finding {
  findingId: string;
  accountId: string;
  region: string;
  resourceId: string;
  resourceType: string;
  status: FindingStatus;
  daysIdle: number;
  monthlyBurn: number;
  dailyBurn: number;
  metadata: Record<string, unknown>;
  scanId?: string;
  updatedAt: number;
}

export interface FindingsSummary {
  totalMonthlyWaste: number;
  totalFlagged: number;
  activeAccounts: number;
  accounts: string[];
}

export interface FindingsResponse {
  findings: Finding[];
  summary: FindingsSummary;
}

export interface Account {
  accountId: string;
  name: string;
  externalId: string;
  regions: string[];
  scanRoleArn?: string | null;
  execRoleArn?: string | null;
  enabled: boolean;
}

export interface ExecutionResult {
  findingId: string;
  status: string;
  reason?: string;
  snapshotId?: string;
  receipt?: string;
}

export interface ExecutionResponse {
  results: ExecutionResult[];
  deleted: number;
  requested: number;
}
