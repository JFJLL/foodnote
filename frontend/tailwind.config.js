/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        herb: "#2F6B4F",
        tomato: "#D94E38",
        ginger: "#D89B32",
        ink: "#1E2722",
        mist: "#F5F7F2"
      },
      boxShadow: {
        soft: "0 18px 45px rgba(39, 56, 43, 0.10)"
      }
    }
  },
  plugins: []
};
