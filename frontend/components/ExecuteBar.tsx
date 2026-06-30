import { usd } from "@/lib/format";

interface Props {
  approvedCount: number;
  approvedBurn: number;
  busy: boolean;
  onExecute: () => void;
}

export function ExecuteBar({ approvedCount, approvedBurn, busy, onExecute }: Props) {
  if (approvedCount === 0) return null;
  return (
    <div className="sticky bottom-4 z-10 flex items-center justify-between rounded-xl border border-sky-500/40 bg-panel/95 p-4 shadow-lg backdrop-blur">
      <div className="text-sm text-slate-300">
        <span className="font-semibold text-sky-300">{approvedCount}</span> resource
        {approvedCount === 1 ? "" : "s"} approved ·{" "}
        <span className="font-semibold text-emerald-300">{usd(approvedBurn)}/mo</span> recoverable
      </div>
      <button
        disabled={busy}
        onClick={onExecute}
        className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-500 disabled:opacity-50"
      >
        {busy ? "Working…" : "Execute Approved Deletions"}
      </button>
    </div>
  );
}
