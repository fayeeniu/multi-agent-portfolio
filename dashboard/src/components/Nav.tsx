"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Overview", icon: "overview" as const },
  { href: "/companies", label: "Companies", icon: "companies" as const },
  { href: "/reports", label: "Reports", icon: "reports" as const },
];

function NavIcon({ name }: { name: (typeof LINKS)[number]["icon"] }) {
  if (name === "overview") {
    return (
      <svg className="nav-icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
        <rect x="2.5" y="2.5" width="6.5" height="6.5" rx="1.6" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <rect x="11" y="2.5" width="6.5" height="6.5" rx="1.6" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <rect x="2.5" y="11" width="6.5" height="6.5" rx="1.6" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <rect x="11" y="11" width="6.5" height="6.5" rx="1.6" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    );
  }
  if (name === "companies") {
    return (
      <svg className="nav-icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
        <path
          d="M3.5 16.5V7.2L10 3.5l6.5 3.7v9.3H3.5Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <path d="M8 16.5v-5h4v5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    );
  }
  return (
    <svg className="nav-icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path
        d="M5 3.5h7.2L16.5 8v8.5H5V3.5Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M12 3.5V8h4.5M7.5 11h5M7.5 13.8h3.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="nav" aria-label="Primary">
      {LINKS.map((link) => {
        const active =
          link.href === "/"
            ? pathname === "/" || pathname === "/mock"
            : pathname.startsWith(link.href);
        return (
          <Link key={link.href} href={link.href} aria-current={active ? "page" : undefined}>
            <NavIcon name={link.icon} />
            <span className="nav-text">{link.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
