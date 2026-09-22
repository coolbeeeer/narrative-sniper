/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        copper: {
          50: '#fef7ed',
          100: '#fdedd6',
          200: '#fad5ad',
          300: '#f6b678',
          400: '#f19143',
          500: '#ec721c',
          600: '#de5c12',
          700: '#b84510',
          800: '#933915',
          900: '#763115',
          950: '#3e1509',
        },
      },
      fontFamily: {
        sans: ['Geist', 'system-ui', 'sans-serif'],
        display: ['Lyon Text', 'Georgia', 'serif'],
      },
      animation: {
        'spring-in': 'spring-in 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        'stagger-in': 'stagger-in 0.4s cubic-bezier(0.16, 1, 0.3, 1) both',
      },
      keyframes: {
        'spring-in': {
          '0%': { opacity: '0', transform: 'translateY(10px) scale(0.98)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        'stagger-in': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}