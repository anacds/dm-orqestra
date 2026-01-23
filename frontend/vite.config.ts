import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";


export default defineConfig(({ mode }) => {
  const apiGatewayUrl = process.env.VITE_API_GATEWAY_URL || 
                        (process.env.DOCKER_CONTAINER ? "http://api-gateway:8000" : "http://localhost:8000");
  
  console.log("[Vite Config] API Gateway URL:", apiGatewayUrl);
  console.log("[Vite Config] DOCKER_CONTAINER:", process.env.DOCKER_CONTAINER);
  
  return {
    publicDir: "public",
    server: {
      host: "0.0.0.0",
      port: 3000,
      proxy: {
        "/api": {
          target: apiGatewayUrl,
          changeOrigin: true,
          secure: false,
          ws: true, 
          configure: (proxy, _options) => {
            proxy.on("proxyReq", (proxyReq, req, _res) => {
              console.log("[Vite Proxy] Proxying:", req.method, req.url, "->", proxyReq.path);
            });
            proxy.on("error", (err, _req, res) => {
              console.error("[Vite Proxy] Error:", err.message);
            });
          },
        },
      },
      fs: {
        allow: [".."],
        deny: [".env", ".env.*", "*.{crt,pem}", "**/.git/**"],
      },
    },
    build: {
      outDir: "dist/spa",
    },
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "."),
        "@shared": path.resolve(__dirname, "./shared"),
      },
    },
    appType: "spa",
  };
});

