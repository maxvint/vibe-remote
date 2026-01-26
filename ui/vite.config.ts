import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '^/(config|settings|status|health|control|doctor|logs|version|upgrade|cli|slack|opencode|ui/reload|github)': {
        target: 'http://localhost:5123',
      },
    },
  },
})
