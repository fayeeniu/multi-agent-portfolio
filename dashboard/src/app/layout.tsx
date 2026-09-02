import type { Metadata, Viewport } from "next";
import Link from "next/link";
import Script from "next/script";
import { Nav } from "@/components/Nav";
import { Masthead } from "@/components/Masthead";
import { BoundaryTag } from "@/components/BoundaryTag";
import "@/styles/globals.css";
import "@/styles/graph.css";

export const metadata: Metadata = {
  title: {
    default: "Research control room",
    template: "%s · Research control room",
  },
  description:
    "Operating surface for a bounded multi-agent company research workflow with named human approval.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#14151a",
};

const THEME_BOOT = `(function(){try{var t=localStorage.getItem("research-theme");document.documentElement.dataset.theme=(t==="light"||t==="dark")?t:"dark";}catch(e){document.documentElement.dataset.theme="dark";}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning data-theme="dark">
      <body>
        <Script id="theme-boot" strategy="beforeInteractive">
          {THEME_BOOT}
        </Script>
        <a className="skip-link" href="#main">
          Skip to main content
        </a>
        <div className="shell">
          <aside className="sidebar">
            <Link className="brand" href="/">
              <span className="brand-copy">
                <span className="brand-name">Research</span>
                <span className="brand-sub">Control room</span>
              </span>
            </Link>
            <Nav />
            <Link className="btn sidebar-cta" data-variant="primary" href="/companies">
              New company
            </Link>
            <div className="sidebar-note">
              <p>Every profile traces to captured evidence and a named review.</p>
              <BoundaryTag />
            </div>
          </aside>
          <div className="workspace">
            <Masthead />
            <main id="main" tabIndex={-1}>
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
