import { createHash } from "node:crypto";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [
    react(),
    {
      name: "inline-script-csp-hashes",
      // Vite injects a React refresh preamble in development. Authorise only its
      // exact content, keeping script-src strict in development and in the build.
      transformIndexHtml: {
        order: "post",
        handler(html) {
          const hashes = [
            ...html.matchAll(
              /<script\b(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g,
            ),
          ].map(
            (match) =>
              `'sha256-${createHash("sha256").update(match[1]).digest("base64")}'`,
          );
          return html.replace(
            "script-src 'self'",
            `script-src 'self' ${hashes.join(" ")}`,
          );
        },
      },
    },
  ],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.API_PROXY_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
    headers: {
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
    },
  },
});
