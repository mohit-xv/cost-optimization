import { usd } from "@/lib/format";
import type { FindingsSummary } from "@/lib/types";

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-xl border border-edge bg-panel p-5">
      <div className="text-sm text-slate-400">{label}</div>
      <div className={`mt-2 text-3xl font-semibold ${accent ?? "text-slate-100"}`}>
        {value}
      </div>
    </div>
  );
}

export function SummaryBanner({ summary }: { summary: FindingsSummary }) {
  const view = summary.activeAccounts <= 1 ? "Single account" : "Organization";
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <Stat
        label="Total Monthly Waste"
        value={usd(summary.totalMonthlyWaste)}
        accent="text-rose-400"
      />
      <Stat label="Flagged Resources" value={String(summary.totalFlagged)} />
      <Stat label={`Active Accounts · ${view}`} value={String(summary.activeAccounts)} />
    </div>
  );
}
