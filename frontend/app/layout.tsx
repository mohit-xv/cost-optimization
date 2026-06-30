import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Nav } from "@/components/Nav";

export const metadata: Metadata = {
  title: "AWS Cost Killer",
  description:
    "FinOps automation — discover idle AWS resources, see cash burn, and kill cloud waste with human-approved deletions.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Nav />
        <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
