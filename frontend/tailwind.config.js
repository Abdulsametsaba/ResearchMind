/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        canvas: '#090d16',
        card: '#0f1422',
        borderDark: '#1e2638',
      },
      animation: {
        'pulse-glow': 'pulseGlow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'flow-light': 'flowLight 2.5s linear infinite',
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { opacity: 0.9, filter: 'drop-shadow(0 0 15px rgba(56, 189, 248, 0.6))' },
          '50%': { opacity: 0.4, filter: 'drop-shadow(0 0 5px rgba(56, 189, 248, 0.2))' },
        },
        flowLight: {
          '0%': { strokeDashoffset: '100' },
          '100%': { strokeDashoffset: '0' },
        }
      }
    },
  },
  plugins: [],
}
