import { shortId, usd } from "@/lib/format";
import type { Finding } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";

interface Props {
  findings: Finding[];
  busyId: string | null;
  onApprove: (id: string) => void;
  onIgnore: (id: string) => void;
}

export function FindingsTable({ findings, busyId, onApprove, onIgnore }: Props) {
  if (findings.length === 0) {
    return (
      <div className="rounded-xl border border-edge bg-panel p-10 text-center text-slate-400">
        No findings yet. Run a discovery scan to surface idle resources.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-edge">
      <table className="w-full text-sm">
        <thead className="bg-panel text-left text-slate-400">
          <tr>
            <th className="px-4 py-3 font-medium">Account</th>
            <th className="px-4 py-3 font-medium">Resource</th>
            <th className="px-4 py-3 font-medium">Region</th>
            <th className="px-4 py-3 font-medium text-right">Days Idle</th>
            <th className="px-4 py-3 font-medium text-right">Monthly Burn</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium text-right">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-edge bg-ink/40">
          {findings.map((f) => {
            const busy = busyId === f.findingId;
            return (
              <tr key={f.findingId} className="hover:bg-panel/40">
                <td className="px-4 py-3 font-mono text-xs text-slate-300">{f.accountId}</td>
                <td className="px-4 py-3">
                  <div className="font-mono text-xs text-slate-200">{shortId(f.resourceId)}</div>
                  <div className="text-xs text-slate-500">{f.resourceType}</div>
                </td>
                <td className="px-4 py-3 text-slate-300">{f.region}</td>
                <td className="px-4 py-3 text-right tabular-nums text-slate-300">{f.daysIdle}</td>
                <td className="px-4 py-3 text-right tabular-nums font-medium text-rose-300">
                  {usd(f.monthlyBurn)}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={f.status} />
                </td>
                <td className="px-4 py-3 text-right">
                  {f.status === "PENDING_APPROVAL" ? (
                    <div className="flex justify-end gap-2">
                      <button
                        disabled={busy}
                        onClick={() => onApprove(f.findingId)}
                        className="rounded-md border border-sky-500/40 bg-sky-500/10 px-3 py-1 text-xs text-sky-300 hover:bg-sky-500/20 disabled:opacity-50"
                      >
                        Approve
                      </button>
                      <button
                        disabled={busy}
                        onClick={() => onIgnore(f.findingId)}
                        className="rounded-md border border-edge px-3 py-1 text-xs text-slate-400 hover:text-slate-200 disabled:opacity-50"
                      >
                        Ignore
                      </button>
                    </div>
                  ) : (
                    <span className="text-xs text-slate-600">—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
