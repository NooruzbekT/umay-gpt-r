/** API проксируется на FastAPI, чтобы фронт и бэк жили на одном origin (без CORS, cookie-friendly). */
const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";
export default {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND}/api/:path*` }];
  },
};
