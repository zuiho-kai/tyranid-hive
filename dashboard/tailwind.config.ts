import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        opus:      { primary: '#9b7ebd', light: '#d4c1ec', dark: '#6d5a8c', bg: '#f3eaf8' },
        codex:     { primary: '#5b8c5a', light: '#8fb98e', dark: '#3a5f39', bg: '#eaf6ea' },
        gemini:    { primary: '#5b9bd5', light: '#9cc0e7', dark: '#3a6fa5', bg: '#eaf4fb' },
        dare:      { primary: '#d4a76a', light: '#e8c99b', dark: '#8b6f47', bg: '#fbf5ec' },
        cocreator: { primary: '#e29578', light: '#ffddd2', dark: '#815b5b', bg: '#fff5f2' },
        cafe:      { white: '#fdf8f3', black: '#1e1e24' },
        ww: {
          base:       'var(--ww-bg-base)',
          card:       'var(--ww-bg-card)',
          surface:    'var(--ww-bg-surface)',
          topbar:     'var(--ww-bg-topbar)',
          danger:     'var(--ww-accent-danger)',
          cute:       'var(--ww-accent-cute)',
          success:    'var(--ww-accent-success)',
          info:       'var(--ww-accent-info)',
          'danger-soft': 'var(--ww-danger-soft)',
          'info-soft':   'var(--ww-info-soft)',
          'subtle-soft': 'var(--ww-subtle-soft)',
          'cute-soft':   'var(--ww-cute-soft)',
          'base-overlay':'var(--ww-base-overlay)',
        },
      },
      textColor: {
        ww: {
          main:  'var(--ww-text-main)',
          muted: 'var(--ww-text-muted)',
          dim:   'var(--ww-text-dim)',
        },
      },
      borderColor: {
        ww: {
          subtle: 'var(--ww-border-subtle)',
          active: 'var(--ww-border-active)',
        },
      },
      boxShadowColor: {
        ww: { glow: 'var(--ww-shadow-glow)' },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      borderRadius: {
        base: '16px',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        'cat-bounce': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%':      { transform: 'translateY(-3px)' },
        },
        'cat-shake': {
          '0%, 100%': { transform: 'translateX(0)' },
          '20%':      { transform: 'translateX(-2px)' },
          '40%':      { transform: 'translateX(2px)' },
          '60%':      { transform: 'translateX(-1px)' },
          '80%':      { transform: 'translateX(1px)' },
        },
        'slide-in-right': {
          from: { opacity: '0', transform: 'translateX(12px)' },
          to:   { opacity: '1', transform: 'translateX(0)' },
        },
        'toast-in': {
          from: { opacity: '0', transform: 'translateX(20px)' },
          to:   { opacity: '1', transform: 'translateX(0)' },
        },
        shimmer: {
          from: { backgroundPosition: '-200% 0' },
          to:   { backgroundPosition: '200% 0' },
        },
        'token-pulse': {
          '0%, 100%': { transform: 'scale(1)', opacity: '1' },
          '50%':      { transform: 'scale(1.05)', opacity: '0.8' },
        },
      },
      animation: {
        'fade-in':        'fade-in 0.3s ease-out',
        'cat-bounce':     'cat-bounce 0.8s ease-in-out infinite',
        'cat-shake':      'cat-shake 0.4s ease-in-out',
        'slide-in-right': 'slide-in-right 0.2s ease-out',
        'toast-in':       'toast-in 0.3s ease-out',
        shimmer:          'shimmer 1.5s ease-in-out infinite',
        'token-pulse':    'token-pulse 0.3s ease-out',
      },
    },
  },
  plugins: [],
} satisfies Config
