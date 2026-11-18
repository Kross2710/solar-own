const backendUrl = (process.env.BACKEND_URL || "http://127.0.0.1:8787").replace(
  /\/$/,
  ""
);

module.exports = {
  allowedDevOrigins: ["192.168.1.51"],
  // Assistant replies with tool calls can take ~40 s; the default proxy timeout is 30 s.
  experimental: { proxyTimeout: 120_000 },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};
