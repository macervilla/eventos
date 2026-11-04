import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import type { IncomingMessage, ServerResponse } from "node:http";

const apiVps = process.env.VPS_API_TARGET;

function compartirHtml(dev: boolean, transformar?: (url: string, html: string) => Promise<string>) {
  return async (req: IncomingMessage, res: ServerResponse, next: () => void) => {
    const ruta = new URL(req.url || "/", "http://localhost").pathname;
    const match = ruta.match(/^\/e\/([a-z0-9-]+)(?:\/i\/[A-Za-z0-9_-]+)?\/?$/);
    if (req.method !== "GET" || !match || !req.headers.accept?.includes("text/html")) return next();
    try {
      const backend = process.env.MEDIA_PROXY_TARGET ?? "http://localhost:8009";
      const respuesta = await fetch(`${backend}/compartir/${match[1]}?dev=${dev ? "true" : "false"}`);
      if (!respuesta.ok) return next();
      const html = await respuesta.text();
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.setHeader("Referrer-Policy", "no-referrer");
      res.setHeader("Cache-Control", "no-store");
      res.end(transformar ? await transformar(`/e/${match[1]}`, html) : html);
    } catch { next(); }
  };
}

export default defineConfig({
  plugins: [react(), {
    name: "eventos-metadatos-iniciales",
    configureServer(server) { server.middlewares.use(compartirHtml(true, (url, html) => server.transformIndexHtml(url, html))); },
    configurePreviewServer(server) { server.middlewares.use(compartirHtml(false)); }
  }],
  preview: { port: 5179, strictPort: true, host: "0.0.0.0" },
  server: {
    port: 5179,
    strictPort: true,
    // En Docker sobre Windows los cambios del volumen no generan eventos: se revisa por sondeo
    watch: { usePolling: true, interval: 300 },
    // Las imagenes se guardan con URL relativa /media/...: se piden al backend
    proxy: {
      "/media": {
        target: process.env.MEDIA_PROXY_TARGET ?? "http://localhost:8009",
        changeOrigin: true
      },
      ...(apiVps ? {
        "/api-vps": {
          target: apiVps,
          changeOrigin: true,
          rewrite: (path: string) => path.replace(/^\/api-vps(?=\/|$)/, "")
        }
      } : {})
    }
  }
});
