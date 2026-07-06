import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// 后端代理目标：
// - 本地开发：默认 http://localhost:8000（后端直接跑在本机）
// - Docker dev：通过环境变量 VITE_PROXY_TARGET=http://agentlens-backend:8000 指定
const proxyTarget = process.env.VITE_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: { "@": path.resolve(__dirname, "./src") },
    },
    server: {
        port: 5173,
        proxy: {
            "/api": {
                target: proxyTarget,
                changeOrigin: true,
            },
            "/docs": {
                target: proxyTarget,
                changeOrigin: true,
            },
            "/openapi.json": {
                target: proxyTarget,
                changeOrigin: true,
            },
        },
    },
});
