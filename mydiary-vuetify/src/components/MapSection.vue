<template>
    <section>
        <section-header label="Location" :meta="headerMeta">
            <template #actions>
                <v-btn
                    size="small"
                    variant="text"
                    :append-icon="showTuning ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                    @click="showTuning = !showTuning"
                >
                    Tuning
                </v-btn>
                <v-btn
                    size="small"
                    :loading="syncing"
                    :disabled="!hasTrack || !hasNote"
                    @click="onSyncToNote"
                >
                    Add map to note
                </v-btn>
            </template>
        </section-header>

        <v-expand-transition>
            <v-card v-if="showTuning" variant="tonal" class="mt-2 pa-3">
                <p class="text-caption text-medium-emphasis mb-2">
                    These are the thresholds the rendered map uses too. Tune them
                    here against real days, then move the winners into
                    TrackParams as the new defaults.
                </p>
                <v-row dense>
                    <v-col v-for="s in sliders" :key="s.key" cols="12" sm="6">
                        <v-slider
                            v-model="params[s.key]"
                            :label="s.label"
                            :min="s.min"
                            :max="s.max"
                            :step="s.step"
                            density="compact"
                            hide-details
                            thumb-label
                        />
                    </v-col>
                </v-row>
                <v-btn size="small" variant="text" class="mt-2" @click="resetParams">
                    Reset to defaults
                </v-btn>
            </v-card>
        </v-expand-transition>

        <div ref="mapEl" class="mydiary-map mt-2" />

        <div class="d-flex flex-wrap ga-4 mt-2">
            <div
                v-for="p in periods"
                :key="p.name"
                class="d-flex align-center ga-1 text-caption text-medium-emphasis"
            >
                <span class="legend-dot" :style="{ backgroundColor: p.color }" />
                {{ p.name }} {{ p.hours }}
            </div>
        </div>

        <v-alert
            v-if="error"
            class="mt-2"
            type="error"
            closable
            @click:close="error = ''"
        >
            {{ error }}
        </v-alert>
    </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { owntracksMapToNote, owntracksTrackForDay } from '@/api'
import SectionHeader from '@/components/SectionHeader.vue'

const props = defineProps<{
    dt: string
    joplinNoteId?: string
}>()

// same four periods, same hexes, as the rendered PNG
const periods = [
    { name: 'Morning', hours: '05-12', color: '#1baf7a' },
    { name: 'Afternoon', hours: '12-17', color: '#eb6834' },
    { name: 'Evening', hours: '17-21', color: '#2a78d6' },
    { name: 'Night', hours: '21-05', color: '#4a3aa7' },
]

const DEFAULTS = {
    max_acc: 100,
    stay_radius_m: 150,
    stay_minutes: 20,
    gap_minutes: 45,
    gap_metres: 250,
    dwell_max_kmh: 1,
}
type ParamKey = keyof typeof DEFAULTS

const sliders: {
    key: ParamKey
    label: string
    min: number
    max: number
    step: number
}[] = [
    { key: 'max_acc', label: 'Max accuracy (m)', min: 20, max: 1000, step: 10 },
    { key: 'stay_radius_m', label: 'Stay radius (m)', min: 50, max: 500, step: 10 },
    { key: 'stay_minutes', label: 'Min stay (min)', min: 5, max: 120, step: 5 },
    { key: 'gap_minutes', label: 'Gap threshold (min)', min: 10, max: 180, step: 5 },
    { key: 'gap_metres', label: 'Gap distance (m)', min: 50, max: 2000, step: 50 },
    { key: 'dwell_max_kmh', label: 'Dwell max speed (km/h)', min: 0.1, max: 5, step: 0.1 },
]

const params = reactive({ ...DEFAULTS })
const showTuning = ref(false)
const loading = ref(false)
const syncing = ref(false)
const error = ref('')
const summary = ref('')
const hasTrack = ref(false)

// the day view uses 'does_not_exist' as its no-note sentinel
const hasNote = computed<boolean>(
    () => !!props.joplinNoteId && props.joplinNoteId !== 'does_not_exist',
)

const headerMeta = computed<string>(() => {
    if (summary.value) return summary.value
    return loading.value ? '' : 'No location data for this day'
})

const mapEl = ref<HTMLElement | null>(null)
let map: L.Map | null = null
let layer: L.LayerGroup | null = null

function resetParams() {
    Object.assign(params, DEFAULTS)
}

function formatSummary(p: Record<string, number>): string {
    const km = (p.distance_m ?? 0) / 1000
    const distance = km >= 0.1 ? `${km.toFixed(1)} km` : `${p.distance_m} m`
    const stops = p.num_stays ?? 0
    const parts = [`${distance} · ${stops} stop${stops === 1 ? '' : 's'}`]
    if (p.num_dropped) parts.push(`${p.num_dropped} noisy fixes dropped`)
    return parts.join(' · ')
}

// a stay's circle grows with its duration, as on the rendered map
function stayRadius(minutes: number): number {
    return Math.min(40, Math.max(8, 2.2 * Math.sqrt(Math.max(minutes, 0))))
}

async function loadTrack() {
    if (!map || !layer) return
    loading.value = true
    error.value = ''
    try {
        const gj = (await owntracksTrackForDay(props.dt, params)).data as any
        layer.clearLayers()
        summary.value = gj.features.length ? formatSummary(gj.properties) : ''
        hasTrack.value = gj.features.length > 0
        if (!gj.features.length) return

        const bounds = L.latLngBounds([])
        for (const f of gj.features) {
            const p = f.properties
            if (p.kind === 'link') {
                const coords = f.geometry.coordinates.map(
                    (c: number[]) => [c[1], c[0]] as [number, number],
                )
                L.polyline(coords, {
                    color: p.color,
                    weight: 3,
                    opacity: p.uncertain ? 0.4 : 1,
                    // a dashed link means the route is genuinely unknown
                    dashArray: p.uncertain ? '7 6' : undefined,
                })
                    .bindTooltip(
                        `${p.t_start.slice(11, 16)}–${p.t_end.slice(11, 16)} · ${p.distance_m} m` +
                            (p.uncertain ? ' · route unknown' : ''),
                    )
                    .addTo(layer)
                coords.forEach((c: [number, number]) => bounds.extend(c))
            } else {
                const [lon, lat] = f.geometry.coordinates
                L.circleMarker([lat, lon], {
                    radius: stayRadius(p.duration_minutes),
                    color: p.color,
                    weight: 2,
                    opacity: 0.85,
                    fillColor: p.color,
                    fillOpacity: 0.22,
                })
                    .bindTooltip(
                        `${p.t_start.slice(11, 16)}–${p.t_end.slice(11, 16)} · ${p.duration_label}`,
                    )
                    .addTo(layer)
                bounds.extend([lat, lon])
            }
        }
        if (bounds.isValid()) map.fitBounds(bounds, { padding: [40, 40] })
    } catch (e: any) {
        error.value =
            e?.response?.data?.detail ||
            e?.message ||
            'Could not load location data'
        summary.value = ''
        hasTrack.value = false
    } finally {
        loading.value = false
    }
}

async function onSyncToNote() {
    if (!hasNote.value) return
    syncing.value = true
    error.value = ''
    try {
        await owntracksMapToNote(props.dt, {})
    } catch (e: any) {
        error.value =
            e?.response?.data?.detail ||
            e?.message ||
            'Could not add the map to the note'
    } finally {
        syncing.value = false
    }
}

onMounted(() => {
    if (!mapEl.value) return
    map = L.map(mapEl.value, { scrollWheelZoom: false }).setView([40.77, -73.96], 13)
    L.tileLayer(
        'https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}{r}.png',
        {
            subdomains: 'abcd',
            maxZoom: 20,
            attribution:
                '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        },
    ).addTo(map)
    layer = L.layerGroup().addTo(map)
    loadTrack()
})

onBeforeUnmount(() => {
    map?.remove()
    map = null
    layer = null
})

watch(() => props.dt, loadTrack)
watch(params, loadTrack, { deep: true })
</script>

<style scoped>
.mydiary-map {
    height: 420px;
    width: 100%;
    border-radius: 8px;
    z-index: 0;
}

.legend-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
}
</style>
