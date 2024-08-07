/**
 * main.ts
 *
 * Bootstraps Vuetify and other plugins then mounts the App`
 */

// Components
import App from './App.vue'

// Composables
import { createApp } from 'vue'

// Plugins
import { registerPlugins } from '@/plugins'

const app = createApp(App)

registerPlugins(app)

import { setupCalendar } from 'v-calendar'

// Use calendar defaults (optional)
app.use(setupCalendar, {})

app.mount('#app')
