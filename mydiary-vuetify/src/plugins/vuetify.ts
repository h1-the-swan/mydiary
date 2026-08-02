/**
 * plugins/vuetify.ts
 *
 * Framework documentation: https://vuetifyjs.com`
 */

// Styles
import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles'
import '@/styles/app.css'

// Composables
import { createVuetify } from 'vuetify'

/**
 * The four time-of-day colors are the app's accent vocabulary. They originate in
 * the backend map renderer (`map_render.py`) and are mirrored by MapSection.vue's
 * legend, so a diary day is literally colored by the time its events happened.
 */
const timeOfDay = {
    morning: '#1baf7a',
    afternoon: '#eb6834',
    evening: '#2a78d6',
    night: '#4a3aa7',
}

// https://vuetifyjs.com/en/introduction/why-vuetify/#feature-guides
export default createVuetify({
    theme: {
        themes: {
            light: {
                colors: {
                    // the app's own blue, not the create-vuetify scaffold's
                    primary: timeOfDay.evening,
                    secondary: timeOfDay.morning,
                    // page sits a shade below surface so cards read as objects
                    background: '#f6f7f9',
                    surface: '#ffffff',
                    ...timeOfDay,
                },
            },
        },
    },
    defaults: {
        VBtn: { variant: 'tonal' },
        VCard: { flat: true, rounded: 'lg' },
        VTextField: { variant: 'outlined', density: 'comfortable' },
        VTextarea: { variant: 'outlined', density: 'comfortable' },
        VSelect: { variant: 'outlined', density: 'comfortable' },
        VAutocomplete: { variant: 'outlined', density: 'comfortable' },
        VFileInput: { variant: 'outlined', density: 'comfortable' },
        VDataTable: { density: 'comfortable' },
    },
})
