import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // The service is loopback-only; both spellings of loopback are legitimate here.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  // The control room is a local operator surface for a loopback-only research
  // service. It renders nothing that should ever be cached by an intermediary.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Cache-Control", value: "no-store" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Content-Type-Options", value: "nosniff" },
        ],
      },
    ];
  },
};

export default nextConfig;
