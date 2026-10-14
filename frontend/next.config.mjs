/** @type {import('next').NextConfig} */
const apiUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // The browser talks to the API through the same origin, so the httpOnly refresh
  // cookie works without CORS.
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${apiUrl}/api/v1/:path*` }];
  },
};

export default nextConfig;
