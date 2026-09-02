"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { KeyboardEvent, MouseEvent, ReactNode } from "react";
import { Icon, resolveStatIcon, type StatIconName } from "@/components/Icon";
import { actionTone, actionVerb } from "@/lib/action-verb";
import { statusLabel, statusTone } from "@/lib/format";

export type { StatIconName };

export type StatItem = {
  label: string;
  value: string | number;
  tone?: string;
  hint?: string;
  icon?: StatIconName;
};

export function Pill({
  status,
  tone,
  label,
}: {
  status?: string;
  tone?: string;
  label?: string;
}) {
  const resolved = tone ?? (status ? statusTone(status) : "idle");
  return (
    <span className="pill" data-tone={resolved}>
      {label ?? (status ? statusLabel(status) : "—")}
    </span>
  );
}

export function Panel({
  title,
  eyebrow,
  aside,
  children,
  flush = false,
}: {
  title: string;
  eyebrow?: string;
  aside?: ReactNode;
  children: ReactNode;
  flush?: boolean;
}) {
  return (
    <section className="panel">
      <header className="panel-head">
        <div className="stack-sm" style={{ gap: "var(--space-1)", minWidth: 0 }}>
          {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
          <h2>{title}</h2>
        </div>
        {aside ? <div className="row" style={{ flex: "none" }}>{aside}</div> : null}
      </header>
      <div className={flush ? "panel-body flush" : "panel-body"}>{children}</div>
    </section>
  );
}

export function NextActionBanner({
  label,
  detail,
  href,
  action,
  actionLabel,
  size = "default",
}: {
  label: string;
  detail: string;
  href?: string | null;
  action?: ReactNode;
  actionLabel?: string;
  size?: "default" | "hero";
}) {
  const verb = actionLabel ?? actionVerb(label);
  return (
    <div className="next-action" data-size={size} data-tone={actionTone(label)}>
      <div className="next-action-copy">
        <p className="eyebrow">Next safe action</p>
        <p className="next-action-title">{label}</p>
        <p className="caption">{detail}</p>
      </div>
      {action ??
        (href ? (
          <Link className="btn" data-variant={size === "hero" ? "primary" : undefined} href={href}>
            {verb}
          </Link>
        ) : null)}
    </div>
  );
}

export function StatGrid({ items }: { items: StatItem[] }) {
  return (
    <div className="stat-grid">
      {items.map((item) => {
        const tone = item.tone && item.tone !== "muted" && item.tone !== "idle" ? item.tone : undefined;
        return (
          <div className="stat-card" key={item.label} data-tone={item.tone ?? undefined}>
            <span className="stat-card-head">
              <Icon name={resolveStatIcon(item.label, item.icon)} className="stat-card-icon" />
              <span className="stat-card-label">{item.label}</span>
              {tone ? <i className="stat-card-dot" aria-hidden="true" /> : null}
            </span>
            <span className="stat-card-value">{item.value}</span>
            {item.hint ? <span className="stat-card-hint">{item.hint}</span> : null}
          </div>
        );
      })}
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty stack-sm" style={{ alignItems: "center" }}>
      <p style={{ color: "var(--ink-2)", fontSize: "0.875rem" }}>{title}</p>
      <p style={{ maxWidth: "42ch" }}>{detail}</p>
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="error-note" role="alert">
      {message}
    </div>
  );
}

export function ServiceError({
  title = "The research service could not complete this request.",
  message,
  onRetry,
  secondary,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
  secondary?: ReactNode;
}) {
  return (
    <div className="service-error" role="alert">
      <p>{title}</p>
      <p className="muted">{message}</p>
      <div className="row">
        {onRetry ? (
          <button type="button" className="btn" data-variant="primary" onClick={onRetry}>
            Retry
          </button>
        ) : null}
        {secondary}
      </div>
    </div>
  );
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton-stack" aria-hidden="true">
      {Array.from({ length: lines }).map((_, index) => (
        <div
          key={index}
          className="skeleton-bar"
          style={{ width: index === lines - 1 ? "60%" : "100%" }}
        />
      ))}
    </div>
  );
}

export function BoardSkeleton() {
  return (
    <div className="overview" aria-hidden="true">
      <div className="command-band">
        <div className="next-action" data-size="hero">
          <Skeleton lines={2} />
        </div>
        <div className="stat-grid">
          {Array.from({ length: 4 }).map((_, index) => (
            <div className="stat-card" key={index}>
              <Skeleton lines={2} />
            </div>
          ))}
        </div>
      </div>
      <div className="panel">
        <div className="panel-body">
          <Skeleton lines={5} />
        </div>
      </div>
    </div>
  );
}

export function LedgerRow({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  const router = useRouter();

  function go() {
    router.push(href);
  }

  function onClick(event: MouseEvent<HTMLTableRowElement>) {
    const target = event.target as HTMLElement;
    if (target.closest("a, button")) return;
    go();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTableRowElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      go();
    }
  }

  return (
    <tr className="ledger-row" tabIndex={0} onClick={onClick} onKeyDown={onKeyDown}>
      {children}
    </tr>
  );
}
