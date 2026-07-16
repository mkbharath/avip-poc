import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // shadcn semantic tokens
        background: "var(--background)",
        foreground: "var(--foreground)",
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
        popover: {
          DEFAULT: "var(--popover)",
          foreground: "var(--popover-foreground)",
        },
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          foreground: "var(--secondary-foreground)",
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
        },
        destructive: {
          DEFAULT: "var(--destructive)",
        },
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        sidebar: {
          DEFAULT: "var(--sidebar)",
          foreground: "var(--sidebar-foreground)",
          primary: "var(--sidebar-primary)",
          "primary-foreground": "var(--sidebar-primary-foreground)",
          accent: "var(--sidebar-accent)",
          "accent-foreground": "var(--sidebar-accent-foreground)",
          border: "var(--sidebar-border)",
          ring: "var(--sidebar-ring)",
        },
        // Lam Research brand
        lam: {
          navy: "#1B2A4A",
          "navy-light": "#2A3D63",
          "navy-dark": "#0F1B33",
          green: "#22c55e",
          "green-dark": "#16a34a",
          teal: "#007B8A",
        },
        // Inspection decision colors — vibrant
        avip: {
          pass: "#16a34a",
          fail: "#dc2626",
          review: "#f59e0b",
          info: "#2563eb",
          "pass-light": "#dcfce7",
          "fail-light": "#fef2f2",
          "review-light": "#fef9c3",
        },
      },
      borderRadius: {
        xl: "0.75rem",
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["'Geist Variable'", "Inter", "system-ui", "-apple-system", "sans-serif"],
        heading: ["'Geist Variable'", "Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["'Geist Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        decision: ["4.5rem", { lineHeight: "1.1", fontWeight: "800" }],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02)",
        "card-hover": "0 4px 16px -2px rgba(0, 0, 0, 0.08), 0 2px 4px -2px rgba(0, 0, 0, 0.03)",
        elevated: "0 8px 30px -4px rgba(0, 0, 0, 0.1), 0 4px 10px -5px rgba(0, 0, 0, 0.04)",
        glow: "0 0 20px -5px rgba(34, 197, 94, 0.3)",
      },
      backgroundImage: {
        "sidebar-gradient": "linear-gradient(180deg, #0c1222 0%, #111a2e 100%)",
      },
    },
  },
  plugins: [],
};

export default config;
