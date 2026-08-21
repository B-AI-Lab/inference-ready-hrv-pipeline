/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        lab: {
          bg: "#07060d",
          panel: "rgba(18, 13, 31, 0.72)",
          border: "rgba(190, 147, 255, 0.18)",
          purple: "#a855f7",
          electric: "#c084fc",
          mint: "#5eead4",
          emerald: "#34d399",
          coral: "#fb7185",
          amber: "#fbbf24",
          red: "#f87171"
        }
      },
      boxShadow: {
        glow: "0 0 34px rgba(168, 85, 247, 0.20)",
        mint: "0 0 30px rgba(52, 211, 153, 0.18)",
        coral: "0 0 30px rgba(251, 113, 133, 0.18)"
      }
    },
  },
  plugins: [],
};
