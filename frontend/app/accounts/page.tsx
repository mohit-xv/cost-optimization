"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { getAccessToken, isConfigured } from "@/lib/auth";
import type { Account } from "@/lib/types";

const EMPTY = {
  accountId: "",
  name: "",
  externalId: "",
  regions: "us-east-1",
  scanRoleArn: "",
  execRoleArn: "",
};

export default function AccountsPage() {
  const router = useRouter();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [form, setForm] = useState({ ...EMPTY });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setError(null);
      const res = await api.listAccounts();
      setAccounts(res.accounts);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    if (isConfigured() && !getAccessToken()) {
      router.push("/login");
      return;
    }
    void load();
  }, [load, router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.upsertAccount({
        accountId: form.accountId.trim(),
        name: form.name.trim(),
        externalId: form.externalId.trim(),
        regions: form.regions.split(",").map((r) => r.trim()).filter(Boolean),
        scanRoleArn: form.scanRoleArn.trim() || null,
        execRoleArn: form.execRoleArn.trim() || null,
        enabled: true,
      });
      setForm({ ...EMPTY });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    try {
      await api.deleteAccount(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const field = (key: keyof typeof EMPTY, label: string, placeholder = "") => (
    <label className="block">
      <span className="text-xs text-slate-400">{label}</span>
      <input
        value={form[key]}
        placeholder={placeholder}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        className="mt-1 w-full rounded-md border border-edge bg-ink px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500/60"
      />
    </label>
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-100">Target accounts</h1>
        <p className="text-sm text-slate-400">
          Register accounts running the Cost Killer cross-account roles.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
          {error}
        </div>
      )}

      <form
        onSubmit={submit}
        className="grid grid-cols-1 gap-4 rounded-xl border border-edge bg-panel p-5 sm:grid-cols-2"
      >
        {field("accountId", "Account ID", "123456789012")}
        {field("name", "Name", "Sandbox")}
        {field("externalId", "External ID", "shared secret")}
        {field("regions", "Regions (comma-separated)", "us-east-1,eu-west-1")}
        {field("scanRoleArn", "Scan role ARN (optional)")}
        {field("execRoleArn", "Exec role ARN (optional)")}
        <div className="sm:col-span-2">
          <button
            type="submit"
            disabled={busy || !form.accountId}
            className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-500 disabled:opacity-50"
          >
            {busy ? "Saving…" : "Save account"}
          </button>
        </div>
      </form>

      <div className="overflow-hidden rounded-xl border border-edge">
        <table className="w-full text-sm">
          <thead className="bg-panel text-left text-slate-400">
            <tr>
              <th className="px-4 py-3 font-medium">Account ID</th>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Regions</th>
              <th className="px-4 py-3 font-medium">Enabled</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-edge bg-ink/40">
            {accounts.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                  No accounts registered yet.
                </td>
              </tr>
            ) : (
              accounts.map((a) => (
                <tr key={a.accountId}>
                  <td className="px-4 py-3 font-mono text-xs text-slate-200">{a.accountId}</td>
                  <td className="px-4 py-3 text-slate-300">{a.name}</td>
                  <td className="px-4 py-3 text-slate-300">{a.regions.join(", ")}</td>
                  <td className="px-4 py-3 text-slate-300">{a.enabled ? "Yes" : "No"}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => remove(a.accountId)}
                      className="rounded-md border border-edge px-3 py-1 text-xs text-rose-300 hover:bg-rose-500/10"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
