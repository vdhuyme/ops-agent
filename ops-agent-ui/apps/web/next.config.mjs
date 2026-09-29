/** @type {import('next').NextConfig} */

// LangGraph backend URL — server-side only (no `NEXT_PUBLIC_` prefix), so the
// value is never bundled into the client. Override at build/start time when
// deploying:
//   LANGGRAPH_BACKEND_URL=https://langgraph.internal.company.com next build
const LANGGRAPH_BACKEND_URL =
  process.env.LANGGRAPH_BACKEND_URL || "http://localhost:2024";

const nextConfig = {
  // Build a self-contained server bundle (`server.js` + minimal
  // `node_modules`) under `.next/standalone/`. Used by the Dockerfile.
  output: "standalone",

  // ⚠️ Disable response compression globally. Next.js's compression
  // middleware buffers the upstream body BEFORE gzipping it, which breaks
  // SSE / chunked responses (chat tokens only arrive when the model
  // finishes generating). The app is internal so losing gzip is fine;
  // re-enable later if you ship a public build behind a CDN that gzip-
  // compresses on its own.
  compress: false,

  // Reverse-proxy /api/langgraph/* → LangGraph backend. Browser sees only
  // the Next.js host; the real backend address never leaks.
  async rewrites() {
    return [
      {
        source: "/api/langgraph/:path*",
        destination: `${LANGGRAPH_BACKEND_URL}/:path*`,
      },
    ];
  },

  // Anti-buffering flags: tell any upstream proxy (nginx etc.) not to
  // buffer, and force no caching of the streaming response.
  async headers() {
    return [
      {
        source: "/api/langgraph/:path*",
        headers: [
          { key: "Cache-Control", value: "no-store" },
          { key: "X-Accel-Buffering", value: "no" },
        ],
      },
    ];
  },
};

export default nextConfig;
