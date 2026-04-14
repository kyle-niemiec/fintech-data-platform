import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          50: "#f2f5fa",
          100: "#d9e1ee",
          200: "#b3c3dd",
          300: "#8ca5cd",
          400: "#5d7fb3",
          500: "#3a5d96",
          600: "#2a4878",
          700: "#1f365a",
          800: "#162640",
          900: "#0f1a2e",
        },
        slate: {
          50: "#f7f8fa",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "IBM Plex Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
} satisfies Config;
