"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { handleCallback } from "@/lib/auth";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Read the code from the URL directly (avoids the useSearchParams Suspense boundary).
    const code = new URLSearchParams(window.location.search).get("code");
    if (!code) {
      setError("Missing authorization code.");
      return;
    }
    handleCallback(code)
      .then(() => router.replace("/"))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [router]);

  return (
    <div className="mx-auto mt-24 max-w-md text-center text-slate-300">
      {error ? (
        <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
          {error}
        </div>
      ) : (
        "Signing you in…"
      )}
    </div>
  );
}
