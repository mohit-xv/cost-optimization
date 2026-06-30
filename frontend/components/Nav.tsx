"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { isConfigured, logout } from "@/lib/auth";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/accounts", label: "Accounts" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <header className="border-b border-edge bg-panel/60 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="text-lg">🔪</span>
            <span className="text-slate-100">Cost Killer</span>
          </Link>
          <nav className="flex gap-1">
            {links.map((l) => {
              const active = pathname === l.href;
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  className={`rounded-md px-3 py-1.5 text-sm transition ${
                    active
                      ? "bg-edge text-slate-100"
                      : "text-slate-400 hover:text-slate-100"
                  }`}
                >
                  {l.label}
                </Link>
              );
            })}
          </nav>
        </div>
        {isConfigured() && (
          <button
            onClick={() => logout()}
            className="rounded-md px-3 py-1.5 text-sm text-slate-400 hover:text-slate-100"
          >
            Sign out
          </button>
        )}
      </div>
    </header>
  );
}
