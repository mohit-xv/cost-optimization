import { getAccessToken } from "@/lib/auth";
import { mockApi } from "@/lib/mock";
import type {
  Account,
  ExecutionResponse,
  FindingsResponse,
} from "@/lib/types";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

// Serve in-memory demo data only when explicitly opted in, or in local dev with no
// backend configured. A PRODUCTION build with a missing API URL must NOT silently mock
// (it would report fake "deletions") — it falls through to real calls and surfaces errors.
export const IS_MOCK =
  process.env.NEXT_PUBLIC_USE_MOCK === "true" ||
  (!BASE && process.env.NODE_ENV !== "production");

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401 || res.status === 403) {
    throw new Error("Unauthorized — please sign in again.");
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return (await res.json()) as T;
}

const realApi = {
  listFindings: (params?: { status?: string; accountId?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.accountId) q.set("accountId", params.accountId);
    const qs = q.toString();
    return apiFetch<FindingsResponse>(`/findings${qs ? `?${qs}` : ""}`);
  },
  approve: (id: string) =>
    apiFetch<{ updated: boolean }>(`/findings/${encodeURIComponent(id)}/approve`, {
      method: "POST",
    }),
  ignore: (id: string) =>
    apiFetch<{ updated: boolean }>(`/findings/${encodeURIComponent(id)}/ignore`, {
      method: "POST",
    }),
  runScan: () => apiFetch<unknown>(`/scan`, { method: "POST", body: "{}" }),
  execute: (findingIds: string[], dryRun: boolean) =>
    apiFetch<ExecutionResponse>(`/execute`, {
      method: "POST",
      body: JSON.stringify({ findingIds, dryRun }),
    }),
  listAccounts: () => apiFetch<{ accounts: Account[] }>(`/accounts`),
  upsertAccount: (account: Partial<Account>) =>
    apiFetch<Account>(`/accounts`, {
      method: "POST",
      body: JSON.stringify(account),
    }),
  deleteAccount: (id: string) =>
    apiFetch<{ deleted: boolean }>(`/accounts/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
};

export const api = IS_MOCK ? mockApi : realApi;
