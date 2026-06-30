"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, IS_MOCK } from "@/lib/api";
import { getAccessToken, isConfigured } from "@/lib/auth";
import { usd } from "@/lib/format";
import type { ExecutionResult, FindingsResponse } from "@/lib/types";
import { SummaryBanner } from "@/components/SummaryBanner";
import { FindingsTable } from "@/components/FindingsTable";
import { ExecuteBar } from "@/components/ExecuteBar";

type ExecStage = "idle" | "previewing" | "confirm" | "executing" | "done";

export default function DashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<FindingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [stage, setStage] = useState<ExecStage>("idle");
  const [preview, setPreview] = useState<ExecutionResult[] | null>(null);
  const [results, setResults] = useState<ExecutionResult[] | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      setData(await api.listFindings());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isConfigured() && !getAccessToken()) {
      router.push("/login");
      return;
    }
    void load();
  }, [load, router]);

  const findings = data?.findings ?? [];
  const approved = useMemo(
    () => findings.filter((f) => f.status === "APPROVED"),
    [findings]
  );
  const approvedBurn = useMemo(
    () => approved.reduce((sum, f) => sum + f.monthlyBurn, 0),
    [approved]
  );

  const act = async (fn: () => Promise<unknown>, id: string) => {
    setBusyId(id);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const runScan = async () => {
    setScanning(true);
    try {
      await api.runScan();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setScanning(false);
    }
  };

  const startExecute = async () => {
    setStage("previewing");
    setPreview(null);
    setResults(null);
    try {
      const res = await api.execute(approved.map((f) => f.findingId), true);
      setPreview(res.results);
      setStage("confirm");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStage("idle");
    }
  };

  const confirmExecute = async () => {
    setStage("executing");
    try {
      const res = await api.execute(approved.map((f) => f.findingId), false);
      setResults(res.results);
      setStage("done");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStage("confirm");
    }
  };

  const closeModal = () => {
    setStage("idle");
    setPreview(null);
    setResults(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">Cost Killer Dashboard</h1>
          <p className="text-sm text-slate-400">
            Idle and orphaned AWS resources, ranked by monthly cash burn.
          </p>
        </div>
        <button
          onClick={runScan}
          disabled={scanning}
          className="rounded-lg border border-edge bg-panel px-4 py-2 text-sm font-medium text-slate-100 hover:bg-edge disabled:opacity-50"
        >
          {scanning ? "Scanning…" : "Run discovery scan"}
        </button>
      </div>

      {IS_MOCK && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
          Demo data — no backend configured. Set <code>NEXT_PUBLIC_API_BASE_URL</code> in{" "}
          <code>frontend/.env.local</code> to connect to your deployed AWS backend.
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
          {error}
        </div>
      )}

      {data && <SummaryBanner summary={data.summary} />}

      {loading ? (
        <div className="rounded-xl border border-edge bg-panel p-10 text-center text-slate-400">
          Loading…
        </div>
      ) : (
        <FindingsTable
          findings={findings}
          busyId={busyId}
          onApprove={(id) => act(() => api.approve(id), id)}
          onIgnore={(id) => act(() => api.ignore(id), id)}
        />
      )}

      <ExecuteBar
        approvedCount={approved.length}
        approvedBurn={approvedBurn}
        busy={stage === "previewing" || stage === "executing"}
        onExecute={startExecute}
      />

      {stage !== "idle" && (
        <ExecuteModal
          stage={stage}
          preview={preview}
          results={results}
          approvedCount={approved.length}
          approvedBurn={approvedBurn}
          onConfirm={confirmExecute}
          onClose={closeModal}
        />
      )}
    </div>
  );
}

function ResultRow({ r }: { r: ExecutionResult }) {
  const ok = r.status === "DELETED" || r.status === "DRY_RUN_OK";
  return (
    <li className="flex items-center justify-between gap-3 border-b border-edge py-2 text-sm last:border-0">
      <span className="font-mono text-xs text-slate-300">{r.findingId}</span>
      <span className={ok ? "text-emerald-300" : "text-amber-300"}>
        {r.status}
        {r.reason ? ` · ${r.reason}` : ""}
      </span>
    </li>
  );
}

function ExecuteModal({
  stage,
  preview,
  results,
  approvedCount,
  approvedBurn,
  onConfirm,
  onClose,
}: {
  stage: ExecStage;
  preview: ExecutionResult[] | null;
  results: ExecutionResult[] | null;
  approvedCount: number;
  approvedBurn: number;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-lg rounded-xl border border-edge bg-panel p-6">
        {stage === "previewing" && (
          <p className="text-slate-300">Running dry-run validation…</p>
        )}

        {stage === "confirm" && (
          <>
            <h2 className="text-lg font-semibold text-slate-100">Confirm deletion</h2>
            <p className="mt-1 text-sm text-slate-400">
              Dry-run passed for the resources below. This will delete{" "}
              <span className="font-semibold text-rose-300">{approvedCount}</span> resource
              {approvedCount === 1 ? "" : "s"} (a recovery snapshot is taken first), saving{" "}
              <span className="font-semibold text-emerald-300">{usd(approvedBurn)}/mo</span>.
            </p>
            <ul className="mt-4 max-h-56 overflow-auto">
              {preview?.map((r) => <ResultRow key={r.findingId} r={r} />)}
            </ul>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={onClose}
                className="rounded-lg border border-edge px-4 py-2 text-sm text-slate-300 hover:text-slate-100"
              >
                Cancel
              </button>
              <button
                onClick={onConfirm}
                className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-500"
              >
                Confirm delete
              </button>
            </div>
          </>
        )}

        {stage === "executing" && (
          <p className="text-slate-300">Deleting approved resources…</p>
        )}

        {stage === "done" && (
          <>
            <h2 className="text-lg font-semibold text-slate-100">Execution complete</h2>
            <ul className="mt-4 max-h-56 overflow-auto">
              {results?.map((r) => <ResultRow key={r.findingId} r={r} />)}
            </ul>
            <div className="mt-6 flex justify-end">
              <button
                onClick={onClose}
                className="rounded-lg border border-edge px-4 py-2 text-sm text-slate-100 hover:bg-edge"
              >
                Close
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
