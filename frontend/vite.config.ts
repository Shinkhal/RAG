import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const { RAG_API_TARGET = "http://127.0.0.1:8000" } = loadEnv(mode, ".", "RAG_");
  return {
    plugins: [react()],
    server: {
      strictPort: true,
      proxy: { "/api": RAG_API_TARGET },
    },
  };
});
