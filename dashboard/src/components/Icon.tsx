import type { ReactNode, SVGProps } from "react";

export type StatIconName =
  | "identity-hold"
  | "activity"
  | "review"
  | "withheld"
  | "building"
  | "badge-check"
  | "hourglass"
  | "layers"
  | "inbox"
  | "compare"
  | "quote"
  | "file-check"
  | "versions"
  | "document";

const LABEL_ICONS: Record<string, StatIconName> = {
  "Identity holds": "identity-hold",
  "Runs executing": "activity",
  "Awaiting review": "review",
  "Sources withheld": "withheld",
  "Companies": "building",
  "Identity resolved": "badge-check",
  "Open decisions": "hourglass",
  "With research runs": "layers",
  "Sources captured": "inbox",
  "Contradictions": "compare",
  "Claims admitted": "quote",
  "Approved exports": "file-check",
  "Approved profiles": "file-check",
  "Report versions": "versions",
  "Claims represented": "document",
  "Research runs": "activity",
  "Profile versions": "versions",
};

export function resolveStatIcon(label: string, icon?: StatIconName): StatIconName {
  return icon ?? LABEL_ICONS[label] ?? "document";
}

const GLYPHS: Record<StatIconName, ReactNode> = {
  "identity-hold": (
    <>
      <path d="M4.5 7.25h15A1.5 1.5 0 0 1 21 8.75v8.5a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.25v-8.5A1.5 1.5 0 0 1 4.5 7.25Z" />
      <circle cx="8.6" cy="12.4" r="1.7" />
      <path d="M6.4 16.4c.35-1.35 1.25-2 2.2-2s1.85.65 2.2 2" />
      <path d="M13.6 11.15h4.2M13.6 14.2h3.1" />
    </>
  ),
  activity: <path d="M3.5 12h3.4l2.3-6.2 3.6 12.4 2.2-6.2H20.5" />,
  review: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M8.4 12.15 10.7 14.4 15.6 9.3" />
    </>
  ),
  withheld: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M6.5 17.5 17.5 6.5" />
    </>
  ),
  building: (
    <>
      <path d="M4.75 20.25V8.4L12 4.4l7.25 4v11.85H4.75Z" />
      <path d="M9.5 20.25v-4.6h5v4.6" />
      <path d="M8.2 10.6h1.6M14.2 10.6h1.6M8.2 13.7h1.6M14.2 13.7h1.6" />
    </>
  ),
  "badge-check": (
    <>
      <path d="M12 3.6 14.15 5.1l2.6.35.85 2.5 2.05 1.7-2.05 1.7-.85 2.5-2.6.35L12 16.7l-2.15-1.5-2.6-.35-.85-2.5-2.05-1.7 2.05-1.7.85-2.5 2.6-.35L12 3.6Z" />
      <path d="M9.15 10.15 11.1 12.1l3.75-3.85" />
    </>
  ),
  hourglass: (
    <>
      <path d="M6.5 3.75h11" />
      <path d="M6.5 20.25h11" />
      <path d="M8 3.75v2.4c0 1.7 1.15 2.85 2.55 3.7L12 10.7l1.45-.85C14.85 9 16 7.85 16 6.15v-2.4" />
      <path d="M8 20.25v-2.4c0-1.7 1.15-2.85 2.55-3.7L12 13.3l1.45.85C14.85 15 16 16.15 16 17.85v2.4" />
    </>
  ),
  layers: (
    <>
      <path d="M12 4.4 3.75 8.75 12 13.1l8.25-4.35L12 4.4Z" />
      <path d="M3.75 12.15 12 16.5l8.25-4.35" />
      <path d="M3.75 15.55 12 19.9l8.25-4.35" />
    </>
  ),
  inbox: (
    <>
      <path d="M4.25 13.1 6.6 5.25h10.8l2.35 7.85v5.9H4.25v-5.9Z" />
      <path d="M4.25 13.1h4.15l1.2 2.15h4.8l1.2-2.15h4.15" />
    </>
  ),
  compare: (
    <>
      <circle cx="6.6" cy="6.6" r="2.1" />
      <circle cx="17.4" cy="17.4" r="2.1" />
      <path d="M6.6 8.7v4.7c0 1.2.95 2.15 2.15 2.15H14.4" />
      <path d="M17.4 15.3v-4.7c0-1.2-.95-2.15-2.15-2.15H9.6" />
    </>
  ),
  quote: (
    <>
      <path d="M8.4 16.8c-2.05 0-3.55-1.45-3.55-3.85V8.2H9.2v4.35H7.55c0 1.55.35 2.35 1.45 2.85-.2.45-.4.9-.6 1.4Z" />
      <path d="M16.55 16.8c-2.05 0-3.55-1.45-3.55-3.85V8.2h4.35v4.35h-1.65c0 1.55.35 2.35 1.45 2.85-.2.45-.4.9-.6 1.4Z" />
    </>
  ),
  "file-check": (
    <>
      <path d="M6.25 3.75h7.1L18.5 8.9v11.35H6.25V3.75Z" />
      <path d="M13.2 3.75V9h5.3" />
      <path d="M8.7 14.35 10.85 16.4 15.4 11.7" />
    </>
  ),
  versions: (
    <>
      <rect x="7.25" y="4.5" width="12" height="14.75" rx="1.4" />
      <path d="M5.25 8.1v10.1c0 .85.7 1.55 1.55 1.55H16.4" />
      <path d="M10.1 9.2h6.1M10.1 12.35h6.1M10.1 15.5h3.9" />
    </>
  ),
  document: (
    <>
      <path d="M6.25 3.75h7.35L18.5 8.65v11.6H6.25V3.75Z" />
      <path d="M13.4 3.75V8.8h5.1" />
      <path d="M8.7 12.2h6.6M8.7 15.3h4.6" />
    </>
  ),
};

export function Icon({
  name,
  className,
  ...props
}: { name: StatIconName } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {GLYPHS[name]}
    </svg>
  );
}
