/** Palette from the brief. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {
    colors: { navy: "#17324D", teal: { DEFAULT: "#16A6A0", dark: "#0F837E" }, mint: "#E8F7F4", paper: "#F7F9FC",
      ink: "#17212B", muted: "#718096", ok: "#269B68", warn: "#F0A43A", bad: "#DC5555" },
    fontFamily: { sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"] },
    boxShadow: { card: "0 1px 2px rgba(23,50,77,.06), 0 4px 14px rgba(23,50,77,.07)" },
  } },
  plugins: [],
};
