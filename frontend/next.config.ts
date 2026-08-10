import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emits `.next/standalone` — a minimal server.js plus only the traced node_modules —
  // so the runtime image carries no dev dependencies and no npm install. Required by
  // the Dockerfile; `npm run dev` and `npm run start` are unaffected.
  output: "standalone",
};

export default nextConfig;
