/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./templates/**/*.js",
    "./static/**/*.js"
  ],
  theme: {
    extend: {
      colors: {
        background: '#1E2836',
        primary: {
          50: '#f5f7ff',
          100: '#ebf0fe',
          200: '#dde5fd',
          300: '#c4d1fb',
          400: '#9ab3f8',
          500: '#6d8ef4',
          600: '#3d64ef',
          700: '#1d45e3',
          800: '#1937b9',
          900: '#162a82',
          950: '#0f1947'
        },
        accent: {
          light: '#4ade80',
          DEFAULT: '#22c55e',
          dark: '#16a34a'
        },
        neon: {
          DEFAULT: '#00FF94',
          50: '#E5FFF4',
          100: '#D1FFE9',
          200: '#A3FFD3',
          300: '#75FFBD',
          400: '#47FFA7',
          500: '#00FF94',
          600: '#00D67A',
          700: '#00A35D',
          800: '#007042',
          900: '#004D2D'
        },
        dark: {
          DEFAULT: '#1E2836',
          100: '#273545',
          200: '#2F3E4F',
          300: '#384859',
          400: '#455668'
        },
        highlight: {
          DEFAULT: '#22D3EE',
          dark: '#0891B2'
        }
      },
      animation: {
        'glow': 'glow 2s ease-in-out infinite alternate',
        'float': 'float 3s ease-in-out infinite',
        'pulse-subtle': 'pulse-subtle 4s ease-in-out infinite',
        'slide-up': 'slide-up 0.5s ease-out',
        'slide-in': 'slideIn 0.5s ease-out',
        'fade-in': 'fadeIn 0.3s ease-out',
        'glow-pulse': 'glowPulse 2s infinite',
        'tilt': 'tilt 10s infinite linear',
        'card-hover': 'cardHover 0.3s ease-out forwards',
        'search-glow': 'searchGlow 2s infinite',
        'metric-slide': 'metricSlide 0.6s ease-out forwards',
        'typing': 'typing 3.5s steps(40, end), blink .75s step-end infinite',
        'tilt-float': 'tiltFloat 6s ease-in-out infinite'
      },
      keyframes: {
        glow: {
          '0%': {
            boxShadow: '0 0 20px rgba(0, 220, 130, 0.3)',
            transform: 'scale(1)'
          },
          '100%': {
            boxShadow: '0 0 40px rgba(0, 220, 130, 0.6)',
            transform: 'scale(1.02)'
          }
        },
        float: {
          '0%, 100%': {
            transform: 'translateY(0)'
          },
          '50%': {
            transform: 'translateY(-10px)'
          }
        },
        'pulse-subtle': {
          '0%, 100%': {
            opacity: 1
          },
          '50%': {
            opacity: 0.8
          }
        },
        'slide-up': {
          '0%': {
            transform: 'translateY(10px)',
            opacity: 0
          },
          '100%': {
            transform: 'translateY(0)',
            opacity: 1
          }
        },
        slideIn: {
          '0%': { transform: 'translateY(20px)', opacity: 0 },
          '100%': { transform: 'translateY(0)', opacity: 1 }
        },
        fadeIn: {
          '0%': { opacity: 0 },
          '100%': { opacity: 1 }
        },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 20px rgba(34, 211, 238, 0.2)' },
          '50%': { boxShadow: '0 0 30px rgba(34, 211, 238, 0.4)' }
        },
        tilt: {
          '0%, 50%, 100%': {
            transform: 'rotate3d(0, 0, 0, 0deg)',
          },
          '25%': {
            transform: 'rotate3d(0.5, 1, 0, 2deg)',
          },
          '75%': {
            transform: 'rotate3d(0.5, -1, 0, 2deg)',
          },
        },
        cardHover: {
          '0%': {
            transform: 'translateY(0) scale(1)',
            boxShadow: '0 0 0 rgba(0, 255, 148, 0)',
          },
          '100%': {
            transform: 'translateY(-5px) scale(1.01)',
            boxShadow: '0 20px 40px rgba(0, 255, 148, 0.2)',
          },
        },
        searchGlow: {
          '0%, 100%': {
            boxShadow: '0 0 20px rgba(0, 255, 148, 0.3), inset 0 0 10px rgba(0, 255, 148, 0.2)',
          },
          '50%': {
            boxShadow: '0 0 30px rgba(0, 255, 148, 0.5), inset 0 0 15px rgba(0, 255, 148, 0.3)',
          },
        },
        metricSlide: {
          '0%': {
            transform: 'translateY(20px)',
            opacity: 0,
          },
          '100%': {
            transform: 'translateY(0)',
            opacity: 1,
          },
        },
        typing: {
          'from': { width: '0' },
          'to': { width: '100%' }
        },
        blink: {
          '50%': { borderColor: 'transparent' }
        },
        tiltFloat: {
          '0%, 100%': { transform: 'perspective(1000px) rotateX(0) translateY(0)' },
          '50%': { transform: 'perspective(1000px) rotateX(2deg) translateY(-10px)' }
        }
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(circle at center, var(--tw-gradient-stops))',
        'gradient-dark': 'linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.8) 100%)'
      },
      typography: {
        DEFAULT: {
          css: {
            maxWidth: 'none',
            color: '#9ca3af',
            a: {
              color: '#22c55e',
              '&:hover': {
                color: '#4ade80',
              },
            },
          },
        },
      },
    }
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
    require('@tailwindcss/aspect-ratio'),
    require('@tailwindcss/line-clamp'),
  ]
}
