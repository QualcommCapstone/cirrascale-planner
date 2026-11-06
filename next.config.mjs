/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  experimental: {
    // /api/chat builds the OpenUI system prompt server-side (src/lib/openui.ts).
    // react-ui is a client-boundary package, so load it with plain Node require
    // instead of bundling it into the server route.
    serverComponentsExternalPackages: ["@openuidev/react-ui"],
  },
};

export default nextConfig;
