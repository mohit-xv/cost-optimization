"use client";

import { isConfigured, loginRedirect } from "@/lib/auth";

export default function LoginPage() {
  return (
    <div className="mx-auto mt-20 max-w-md rounded-2xl border border-edge bg-panel p-8 text-center">
      <div className="text-4xl">🔪</div>
      <h1 className="mt-3 text-2xl font-semibold text-slate-100">AWS Cost Killer</h1>
      <p className="mt-2 text-sm text-slate-400">
        Sign in to review flagged resources and approve deletions.
      </p>

      {isConfigured() ? (
        <button
          onClick={() => void loginRedirect()}
          className="mt-6 w-full rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-500"
        >
          Sign in with AWS Cognito
        </button>
      ) : (
        <p className="mt-6 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-left text-xs text-amber-300">
          Cognito is not configured. Set <code>NEXT_PUBLIC_COGNITO_DOMAIN</code> and{" "}
          <code>NEXT_PUBLIC_COGNITO_CLIENT_ID</code> in <code>.env.local</code> (from the
          central Terraform outputs).
        </p>
      )}
    </div>
  );
}
