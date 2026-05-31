/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        edge: {
          bg:    '#05070b',
          panel: '#0b0f17',
          card:  '#0f1420',
          line:  '#1a2030',
        },
      },
      animation: {
        'pulse-dot':   'pulseDot 1.6s ease-in-out infinite',
        'pulse-ring':  'pulseRing 2s cubic-bezier(0.22, 0.61, 0.36, 1) infinite',
        'scan':        'scan 4.5s linear infinite',
        'flicker':     'flicker 6s steps(60) infinite',
        'rise':        'rise .55s cubic-bezier(.16,.84,.3,1) both',
        'amber-throb': 'amberThrob 1.4s ease-in-out infinite',
        'reticle':     'reticle 1.2s ease-out forwards',
        'ticker':      'ticker 22s linear infinite',
      },
      keyframes: {
        pulseDot:   { '0%,100%': { opacity: '1' }, '50%': { opacity: '.35' } },
        pulseRing:  { '0%': { transform: 'scale(.6)', opacity: '.7' }, '100%': { transform: 'scale(2.4)', opacity: '0' } },
        scan:       { '0%': { transform: 'translateY(-10%)' }, '100%': { transform: 'translateY(110%)' } },
        flicker:    { '0%,98%,100%': { opacity: '.85' }, '99%': { opacity: '.55' } },
        rise:       {
          '0%':   { transform: 'translateY(24px)', opacity: '0', filter: 'blur(4px)' },
          '100%': { transform: 'translateY(0)',    opacity: '1', filter: 'blur(0)' },
        },
        amberThrob: {
          '0%,100%': { boxShadow: '0 0 0 0 rgba(245,158,11,.45), inset 0 0 24px rgba(245,158,11,.08)' },
          '50%':     { boxShadow: '0 0 30px 2px rgba(245,158,11,.25), inset 0 0 32px rgba(245,158,11,.16)' },
        },
        reticle: {
          '0%':   { transform: 'scale(1.8)', opacity: '0' },
          '60%':  { transform: 'scale(1)',   opacity: '1' },
          '100%': { transform: 'scale(1)',   opacity: '1' },
        },
        ticker: { '0%': { transform: 'translateX(0)' }, '100%': { transform: 'translateX(-50%)' } },
      },
    },
  },
  plugins: [],
}
