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

        <div ref="overviewEl" class="mydiary-map mt-2" />

        <!-- a day spent in two or more distinct areas is saved as several maps:
             this whole-day one, then a panel per area. Show what will be saved. -->
        <div v-if="areas.length" class="area-panels mt-3">
            <figure v-for="area in areas" :key="area.index" class="ma-0">
                <div
                    :ref="(el) => setAreaEl(area.index, el)"
                    class="mydiary-map mydiary-map--panel"
                />
                <figcaption
                    class="d-flex flex-wrap ga-2 mt-1 text-caption text-medium-emphasis"
                >
                    <span class="font-weight-medium">{{ area.label }}</span>
                    <span>{{ areaSummary(area) }}</span>
                </figcaption>
            </figure>
        </div>

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

        <v-alert
            v-if="notice"
            class="mt-2"
            type="success"
            closable
            @click:close="notice = ''"
        >
            {{ notice }}
        </v-alert>
    </section>
</template>

<script setup lang="ts">
import {
    computed,
    nextTick,
    onBeforeUnmount,
    onMounted,
    reactive,
    ref,
    watch,
} from 'vue'
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
const notice = ref('')
const summary = ref('')
const hasTrack = ref(false)

// the day view uses 'does_not_exist' as its no-note sentinel
const hasNote = computed<boolean>(
    () => !!props.joplinNoteId && props.joplinNoteId !== 'does_not_exist',
)

const headerMeta = computed<string>(() => {
    if (!summary.value) return loading.value ? '' : 'No location data for this day'
    // say how many maps this day saves as, since that is no longer always one
    if (!areas.value.length) return summary.value
    return `${summary.value} · ${areas.value.length + 1} maps`
})

type Area = {
    index: number
    label: string
    num_stays: number
    distance_m: number
    bounds: [number, number, number, number] | null
}

const overviewEl = ref<HTMLElement | null>(null)
const areas = ref<Area[]>([])
let map: L.Map | null = null
let layer: L.LayerGroup | null = null
// one Leaflet instance per area panel, keyed by area index
const areaEls = new Map<number, HTMLElement>()
const areaMaps = new Map<number, { map: L.Map; layer: L.LayerGroup }>()
let features: any[] = []

function setAreaEl(index: number, el: unknown) {
    const node = (el as HTMLElement | null) ?? null
    if (node) areaEls.set(index, node)
    else {
        areaMaps.get(index)?.map.remove()
        areaMaps.delete(index)
        areaEls.delete(index)
    }
}

function areaSummary(area: Area): string {
    const km = area.distance_m / 1000
    const distance = km >= 0.1 ? `${km.toFixed(1)} km` : `${area.distance_m} m`
    return `${distance} · ${area.num_stays} stop${area.num_stays === 1 ? '' : 's'}`
}

function basemap(target: L.Map): L.Map {
    L.tileLayer(
        'https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}{r}.png',
        {
            subdomains: 'abcd',
            maxZoom: 20,
            attribution:
                '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        },
    ).addTo(target)
    return target
}

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

/** Draw the given features into a layer, returning what they cover. */
function drawInto(target: L.LayerGroup, feats: any[]): L.LatLngBounds {
    const bounds = L.latLngBounds([])
    for (const f of feats) {
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
                .addTo(target)
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
                .addTo(target)
            bounds.extend([lat, lon])
        }
    }
    return bounds
}

/** Panels are framed on their stays, as the saved images are, so the leg out of
 *  an area runs off the edge instead of dragging the zoom back out. */
function frameOn(target: L.Map, area: Area, fallback: L.LatLngBounds) {
    const b = area.bounds
    if (!b) {
        if (fallback.isValid()) target.fitBounds(fallback, { padding: [40, 40] })
        return
    }
    const [minLat, minLon, maxLat, maxLon] = b
    if (minLat === maxLat && minLon === maxLon) {
        // a single stay has no extent; 15 is where the renderer clamps too
        target.setView([minLat, minLon], 15)
        return
    }
    target.fitBounds(
        L.latLngBounds([minLat, minLon], [maxLat, maxLon]),
        { padding: [40, 40] },
    )
}

async function drawAreaPanels() {
    await nextTick()
    for (const area of areas.value) {
        const el = areaEls.get(area.index)
        if (!el) continue
        let panel = areaMaps.get(area.index)
        if (!panel) {
            const m = basemap(L.map(el, { scrollWheelZoom: false }))
            panel = { map: m, layer: L.layerGroup().addTo(m) }
            areaMaps.set(area.index, panel)
        }
        panel.layer.clearLayers()
        const covered = drawInto(
            panel.layer,
            features.filter((f) => f.properties.area === area.index),
        )
        frameOn(panel.map, area, covered)
        // the div is sized by layout that may not have settled when it was made
        panel.map.invalidateSize()
    }
}

async function loadTrack() {
    if (!map || !layer) return
    loading.value = true
    error.value = ''
    try {
        const gj = (await owntracksTrackForDay(props.dt, params)).data as any
        layer.clearLayers()
        features = gj.features
        summary.value = gj.features.length ? formatSummary(gj.properties) : ''
        hasTrack.value = gj.features.length > 0

        // drop panels for areas this day no longer has before rebuilding
        const next: Area[] = gj.features.length ? (gj.properties.areas ?? []) : []
        for (const [index, panel] of areaMaps) {
            if (!next.some((a) => a.index === index)) {
                panel.map.remove()
                areaMaps.delete(index)
                areaEls.delete(index)
            }
        }
        areas.value = next
        if (!gj.features.length) return

        const bounds = drawInto(layer, gj.features)
        if (bounds.isValid()) map.fitBounds(bounds, { padding: [40, 40] })
        await drawAreaPanels()
    } catch (e: any) {
        error.value =
            e?.response?.data?.detail ||
            e?.message ||
            'Could not load location data'
        summary.value = ''
        hasTrack.value = false
        areas.value = []
    } finally {
        loading.value = false
    }
}

async function onSyncToNote() {
    if (!hasNote.value) return
    syncing.value = true
    error.value = ''
    notice.value = ''
    try {
        const r = (await owntracksMapToNote(props.dt, {})).data as {
            result: string
            num_maps: number
        }
        // a day spent in two or more distinct areas gets a map each, plus the
        // whole-day overview, so say how many actually landed
        const maps = r.num_maps === 1 ? 'the map' : `${r.num_maps} maps`
        notice.value =
            r.result === 'no update'
                ? `The note already has ${maps}`
                : `Added ${maps} to the note`
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
    if (!overviewEl.value) return
    // a world view, not a home one: the map refits to the day's track as soon
    // as it loads, so this is only ever a placeholder, and a real centre here
    // would be a location baked into a public repo
    map = basemap(
        L.map(overviewEl.value, { scrollWheelZoom: false }).setView([0, 0], 2),
    )
    layer = L.layerGroup().addTo(map)
    loadTrack()
})

onBeforeUnmount(() => {
    for (const panel of areaMaps.values()) panel.map.remove()
    areaMaps.clear()
    areaEls.clear()
    map?.remove()
    map = null
    layer = null
})

watch(() => props.dt, loadTrack)
watch(params, loadTrack, { deep: true })
</script>

<style scoped>
/* the area panels sit side by side where there is room, and stack on a phone */
.area-panels {
    display: grid;
    gap: 16px;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
}

.mydiary-map--panel {
    height: 260px;
}

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
