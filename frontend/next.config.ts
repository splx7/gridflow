import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Plotly.js is CommonJS; needs transpilation for Next.js
  transpilePackages: ["react-plotly.js"],
};

export default nextConfig;
