import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactCompiler: true,
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/:path*`,
      },
      {
        source: "/ws",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/ws`,
      },
    ];
  },
};

export default nextConfig;
