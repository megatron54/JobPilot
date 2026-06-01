/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          900: '#0f1729',
          800: '#1a2332',
          700: '#1e2d40',
          600: '#2a3a4e',
          500: '#354a60',
        },
      },
    },
  },
  plugins: [],
}
