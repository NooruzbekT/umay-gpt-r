import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        teal: { DEFAULT: "#2E9EA5", soft: "#DDF1F2", deep: "#0F3B3E" },
        paper: "#F3F7F7",
        dot: "#E5484D",
        steppe: "#E9B44C",
        mist: "#7E9597",
      },
      fontFamily: {
        display: ["Unbounded", "system-ui", "sans-serif"],
        sans: ["'Golos Text'", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
