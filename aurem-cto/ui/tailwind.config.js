/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'cto-bg': '#0a0e1a',
        'cto-card': '#111827',
        'cto-accent': '#fbbf24',
      },
    },
  },
  plugins: [],
}
