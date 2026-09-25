// Unit tests for the plain TS modules (chordpro.ts, chords.ts). Kept apart from
// vite.config.ts so tests don't load the Vuetify plugin they never use.
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'

export default defineConfig({
    resolve: {
        alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    test: {
        include: ['src/**/*.test.ts'],
        environment: 'node',
    },
})
