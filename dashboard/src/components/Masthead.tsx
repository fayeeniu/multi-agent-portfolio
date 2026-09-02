"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useResource } from "@/lib/hooks";
import type { SessionPayload } from "@/lib/types";

const TITLES: { test: (path: string) => boolean; title: string }[] = [
  { test: (path) => path === "/" || path === "/mock", title: "Overview" },
  { test: (path) => path.startsWith("/companies/"), title: "Company" },
  { test: (path) => path.startsWith("/companies"), title: "Companies" },
  { test: (path) => path.startsWith("/reports"), title: "Reports" },
  { test: (path) => path.startsWith("/runs"), title: "Research run" },
];

function initials(name: string | null): string {
  if (!name) return "—";
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function Masthead() {
  const pathname = usePathname();
  const { data } = useResource<SessionPayload>("session");
  const match = TITLES.find((item) => item.test(pathname)) ?? { title: "Workbench" };
  const reviewer = data?.system.reviewer ?? null;
  const mode =
    data?.system.research_mode === "live"
      ? "Public research open"
      : data?.system.research_mode === "fixture"
        ? "Fixture research"
        : data
          ? "Research gates closed"
          : "Contacting service";

  return (
    <header className="masthead">
      <div className="page-frame masthead-bar">
        <div className="masthead-title">
          <p className="workspace-title">{match.title}</p>
        </div>
        <span className="masthead-spacer" />
        <ThemeToggle />
        <div className="identity-chip" data-size="sm">
          <span className="identity-avatar" aria-hidden="true">
            {initials(reviewer)}
          </span>
          <span>
            <strong>{reviewer ?? "No reviewer set"}</strong>
            <span className="caption">{mode}</span>
          </span>
        </div>
        <Link className="btn masthead-cta" data-variant="primary" href="/companies">
          New company
        </Link>
      </div>
    </header>
  );
}
