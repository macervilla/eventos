import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5179,
    strictPort: true,
    // En Docker sobre Windows los cambios del volumen no generan eventos: se revisa por sondeo
    watch: { usePolling: true, interval: 300 },
    // Las imagenes se guardan con URL relativa /media/...: se piden al backend
    proxy: {
      "/media": process.env.MEDIA_PROXY_TARGET ?? "http://localhost:8009"
    }
  }
});
