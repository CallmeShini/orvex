import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  devIndicators: false,
  async rewrites() {
    const apiBaseUrl = process.env.ORVEX_API_URL ?? "http://127.0.0.1:8000";
    return [
      {
        source: "/api/orvex/:path*",
        destination: `${apiBaseUrl.replace(/\/$/, "")}/:path*`
      }
    ];
  }
};

export default nextConfig;
