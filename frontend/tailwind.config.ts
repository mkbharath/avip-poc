import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Lam Research brand colors
        lam: {
          navy: "#1B2A4A",
          "navy-light": "#2A3D63",
          "navy-dark": "#0F1B33",
          green: "#00A651",
          "green-light": "#33B873",
          "green-dark": "#008542",
          teal: "#007B8A",
          gray: {
            50: "#F8F9FA",
            100: "#F0F2F5",
            200: "#E2E6EB",
            300: "#CDD3DB",
            400: "#9BA5B3",
            500: "#6B7689",
            600: "#4A5568",
            700: "#2D3748",
            800: "#1A202C",
            900: "#0F1319",
          },
        },
        // Inspection decision colors (preserved)
        avip: {
          pass: "#1E8E3E",
          fail: "#C0392B",
          review: "#E67E22",
          info: "#156082",
          "pass-light": "#d4edda",
          "fail-light": "#f8d7da",
          "review-light": "#fff3cd",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      fontSize: {
        decision: ["4.5rem", { lineHeight: "1.1", fontWeight: "800" }],
      },
    },
  },
  plugins: [],
};

export default config;
