import type { FindingStatus } from "@/lib/types";

const STYLES: Record<FindingStatus, string> = {
  PENDING_APPROVAL: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  APPROVED: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  DELETING: "bg-violet-500/15 text-violet-300 border-violet-500/30",
  DELETED: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  IGNORED: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  FAILED: "bg-rose-500/15 text-rose-300 border-rose-500/30",
};

const LABELS: Record<FindingStatus, string> = {
  PENDING_APPROVAL: "Pending",
  APPROVED: "Approved",
  DELETING: "Deleting",
  DELETED: "Deleted",
  IGNORED: "Ignored",
  FAILED: "Failed",
};

export function StatusBadge({ status }: { status: FindingStatus }) {
  return (
    <span
      className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-medium ${STYLES[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}
