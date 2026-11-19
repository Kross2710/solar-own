import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

export default {
  experimental: { proxyTimeout: 120000 },
  async redirects() {
    return [{ source: "/optimization/accuracy", destination: "/optimization", permanent: false }];
  },
  async rewrites() {
    const origin = (process.env.BACKEND_URL || "http://127.0.0.1:8787").replace(/\/$/, "");
    return { fallback: [{ source: "/api/:path*", destination: origin + "/api/:path*" }] };
  },
  turbopack: { root: dirname(fileURLToPath(import.meta.url)) }
};
