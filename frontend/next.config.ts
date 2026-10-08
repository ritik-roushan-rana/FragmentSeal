import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The UI is a client-rendered console talking to the FastAPI backend over
  // JWT-authenticated fetches, so there is nothing to prerender into a cached
  // shell. Cache Components / Partial Prefetching are left off.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    // Lets the browser call /api/... on the same origin in development.
    const backend = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";
    return [{ source: "/backend/:path*", destination: `${backend}/:path*` }];
  },
};

export default nextConfig;
