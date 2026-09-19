import type { NextConfig } from "next";

// L'API FastAPI n'est jamais exposée au navigateur : le serveur Next relaie
// /api/* vers elle (après vérification de l'identité par proxy.ts).
// ⚠️ Les rewrites sont figés au build : API_INTERNAL_URL doit être posée avant
// `npm run build` (cf. web/Dockerfile).
const API_INTERNAL = process.env.API_INTERNAL_URL || "http://127.0.0.1:8810";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_INTERNAL}/:path*` }];
  },
};

export default nextConfig;
