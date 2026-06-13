import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GitHub Pages serves project sites from /<repo>/ — set base at build time via
// VITE_BASE (the deploy workflow passes it). Defaults to "/" for local dev.
export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  plugins: [react()],
});
