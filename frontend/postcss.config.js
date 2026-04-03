module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
    // Note: PurgeCSS is handled by Tailwind's built-in purge functionality
    // Do NOT add PurgeCSS here as it conflicts with Tailwind's JIT mode
    // Instead, configure purge in tailwind.config.js
  },
}
