import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
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
