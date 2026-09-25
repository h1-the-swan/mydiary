<template>
    <page-shell :eyebrow="song?.artist_name ?? ''" :title="song?.name ?? 'Practice'">
        <template #actions>
            <v-btn-toggle v-if="arrangements.length > 1" v-model="instrument" mandatory density="compact">
                <v-btn v-for="a in arrangements" :key="a.id" :value="a.instrument">
                    {{ INSTRUMENT_LABELS[a.instrument] }}
                </v-btn>
            </v-btn-toggle>
            <v-btn variant="text" :to="{ name: 'performSong', params: { id }, hash: '#arrangements' }">
                Edit sheet
            </v-btn>
        </template>

        <p v-if="loaded && !arrangement" class="text-body-1">
            This song has no sheet yet.
            <router-link :to="{ name: 'performSong', params: { id }, hash: '#arrangements' }">Add one</router-link>
            to practice it.
        </p>

        <template v-if="arrangement">
            <div ref="headBox" class="reading">
                <div v-if="keyLine" class="text-body-1 text-medium-emphasis mb-3">{{ keyLine }}</div>
                <div v-if="!lyricsOnly && parsed.chords.length" class="d-flex flex-wrap ga-2 mb-4">
                    <ChordDiagram
                        v-for="chord in parsed.chords"
                        :key="chord"
                        :chord="chord"
                        :instrument="arrangement.instrument as Instrument"
                        :define="parsed.defines[chord]"
                        :size="72"
                    />
                </div>
                <StructureLine :parsed="parsed" :levels="levels" class="mb-3" @jump="jump" />
                <div class="d-flex flex-wrap align-center ga-4 mb-4">
                    <v-switch v-model="showAll" label="Show everything" color="primary" density="compact" hide-details />
                    <v-switch v-model="lyricsOnly" label="Lyrics only" color="primary" density="compact" hide-details />
                    <v-spacer />
                    <v-btn icon="mdi-format-font-size-decrease" variant="text" size="small" aria-label="Smaller text" @click="bump(-0.1)" />
                    <v-btn icon="mdi-format-font-size-increase" variant="text" size="small" aria-label="Larger text" @click="bump(0.1)" />
                </div>
            </div>

            <div ref="sheetBox" class="practice-sheet" :class="{ 'two-col': twoCol }" @click="onSheetClick">
                <SongSheet
                    :parsed="parsed"
                    :levels="levels"
                    :show-all="showAll"
                    :lyrics-only="lyricsOnly"
                    :scale="scale"
                    @chord="chordShown = $event"
                />
            </div>

            <div ref="doneBox" class="done-bar">
                <v-btn color="primary" variant="flat" size="x-large" rounded="pill" prepend-icon="mdi-check" @click="checking = true">
                    Done
                </v-btn>
            </div>

            <AfterRunCheck
                v-model="checking"
                :section-keys="keys"
                :saving="saving"
                :failed="saveFailed"
                @save="saveRun"
            />

            <v-dialog :model-value="chordShown !== null" max-width="240" @update:model-value="chordShown = null">
                <v-card class="pa-4 d-flex justify-center">
                    <ChordDiagram
                        v-if="chordShown"
                        :chord="chordShown"
                        :instrument="arrangement.instrument as Instrument"
                        :define="parsed.defines[chordShown]"
                        :size="180"
                    />
                </v-card>
            </v-dialog>
            <!-- at the top, so it never covers the Done button -->
            <v-snackbar v-model="savedToast" timeout="2500" location="top">Run saved</v-snackbar>
        </template>
    </page-shell>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AfterRunCheck from '@/components/AfterRunCheck.vue'
import ChordDiagram from '@/components/ChordDiagram.vue'
import PageShell from '@/components/PageShell.vue'
import SongSheet from '@/components/SongSheet.vue'
import StructureLine from '@/components/StructureLine.vue'
import { describeKey, parseSheet, sectionKeys, type Level } from '@/chordpro'
import type { Instrument } from '@/chords'
import { INSTRUMENT_LABELS, levelMap } from '@/practice'
import { useAppStore } from '@/store/app'
import {
    PerformSongRead,
    SongArrangementRead,
    createPracticeRun,
    listSongArrangements,
    readSectionLevels,
} from '@/api'

const props = defineProps<{ id: string | number }>()
const route = useRoute()
const router = useRouter()
const app = useAppStore()

const songId = computed(() => Number(props.id))
const song = ref<PerformSongRead>()
const arrangements = ref<SongArrangementRead[]>([])
const levels = ref<Record<string, Level>>({})
const loaded = ref(false)
const instrument = ref<string>()
const showAll = ref(false)
const lyricsOnly = ref(false)
const checking = ref(false)
const saving = ref(false)
const saveFailed = ref(false)
const savedToast = ref(false)
const chordShown = ref<string | null>(null)

const arrangement = computed(() => arrangements.value.find((a) => a.instrument === instrument.value))
const parsed = computed(() => parseSheet(arrangement.value?.sheet ?? ''))
const keys = computed(() => sectionKeys(parsed.value))
const keyLine = computed(() => (arrangement.value ? describeKey(arrangement.value.key, arrangement.value.capo) : ''))

// text size is a per-device preference, so it lives in this browser only
const SCALE_KEY = 'mydiary.practice.scale'
const DEFAULT_SCALE = 1.25
function readScale(): number {
    try {
        const v = Number(localStorage.getItem(SCALE_KEY))
        return v >= 0.8 && v <= 2.2 ? v : DEFAULT_SCALE
    } catch {
        return DEFAULT_SCALE
    }
}
const scale = ref(readScale())
function bump(delta: number) {
    scale.value = Math.min(2.2, Math.max(0.8, Math.round((scale.value + delta) * 10) / 10))
    try {
        localStorage.setItem(SCALE_KEY, String(scale.value))
    } catch {
        // private window: the size just isn't remembered
    }
}

// Two columns only when the whole sheet fits on screen as two balanced columns.
// Any taller and the second column begins above the fold, so reading it means
// scrolling back up — worse than one column you scroll through once.
const WIDE_LANDSCAPE = '(min-width: 900px) and (orientation: landscape)'
// the sticky Done button's own height, plus its 24px margin and 16px offset
const DONE_BAR_GAP = 40
const sheetBox = ref<HTMLElement>()
const headBox = ref<HTMLElement>()
const doneBox = ref<HTMLElement>()
const twoCol = ref(false)

function fitColumns() {
    const box = sheetBox.value
    const sheet = box?.querySelector<HTMLElement>('.song-sheet')
    if (!box || !sheet || !window.matchMedia(WIDE_LANDSCAPE).matches) {
        twoCol.value = false
        return
    }
    // measure the two-column height without showing it: the class goes on, the
    // read forces a reflow, and it comes off before anything is painted
    const on = box.classList.contains('two-col')
    box.classList.add('two-col')
    const columns = sheet.offsetHeight
    box.classList.toggle('two-col', on)
    const header = box.getBoundingClientRect().top + window.scrollY
    const room = window.innerHeight - header - (doneBox.value?.offsetHeight ?? 0) - DONE_BAR_GAP
    twoCol.value = columns <= room
}

// the sheet's own height changes with these; the header's is watched separately,
// because the chord diagrams draw asynchronously
watch([parsed, levels, lyricsOnly, showAll, scale], fitColumns, { flush: 'post' })

const headSize = new ResizeObserver(() => fitColumns())
watch(headBox, (el, prev) => {
    if (prev) headSize.unobserve(prev)
    if (el) headSize.observe(el)
})

async function loadLevels() {
    levels.value = levelMap((await readSectionLevels(songId.value)).data)
}

async function load() {
    await app.loadPerformSongs()
    song.value = app.getPerformSongById(songId.value)
    arrangements.value = (await listSongArrangements(songId.value)).data
    const wanted = route.query.instrument
    instrument.value = arrangements.value.some((a) => a.instrument === wanted)
        ? (wanted as string)
        : arrangements.value[0]?.instrument
    await loadLevels()
    loaded.value = true
}

watch(instrument, (inst) => {
    if (inst && route.query.instrument !== inst) router.replace({ query: { ...route.query, instrument: inst } })
})

// a fresh check never opens on the last run's error
watch(checking, (open) => {
    if (open) saveFailed.value = false
})

// The after-run check stays open until the run is stored, so nothing is lost
// when the app can't be reached.
async function saveRun(run: { sections: { section_key: string; stumbled: boolean }[]; note: string }) {
    if (!arrangement.value) return
    saving.value = true
    saveFailed.value = false
    try {
        await createPracticeRun({
            perform_song_id: songId.value,
            arrangement_id: lyricsOnly.value ? null : arrangement.value.id,
            note: run.note || null,
            sections: run.sections,
        })
    } catch {
        saveFailed.value = true
        return
    } finally {
        saving.value = false
    }
    checking.value = false
    // the run is stored by now, so a stale level colour must not read as a failed save
    await loadLevels().catch(() => {})
    savedToast.value = true
    // the next run starts at the top of the song
    window.scrollTo({ top: 0, behavior: 'smooth' })
}

function jump(index: number) {
    document.getElementById(`sheet-sec-${index}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function turnPage(direction: 1 | -1) {
    window.scrollBy({ top: direction * window.innerHeight * 0.8, behavior: 'smooth' })
}

// a tap on the lower half of the sheet turns the page; SongSheet stops the
// taps it uses itself (peeks, chord names)
function onSheetClick(event: MouseEvent) {
    if (event.clientY > window.innerHeight / 2) turnPage(1)
}

// a tapped switch keeps focus on its checkbox, so only text entry may swallow a
// key: the pedal has to keep working after "Show everything" is toggled
const TYPELESS_INPUTS = ['checkbox', 'radio', 'button']
function isTextEntry(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) return false
    const field = target.closest('input, textarea, [contenteditable]')
    if (!(field instanceof HTMLElement)) return false
    if (field instanceof HTMLInputElement) return !TYPELESS_INPUTS.includes(field.type)
    return true
}

// page-turner pedals send PageDown/PageUp or arrow keys
function onKey(event: KeyboardEvent) {
    if (checking.value || chordShown.value !== null || isTextEntry(event.target)) return
    if (['PageDown', 'ArrowDown', 'ArrowRight'].includes(event.key)) {
        event.preventDefault()
        turnPage(1)
    } else if (['PageUp', 'ArrowUp', 'ArrowLeft'].includes(event.key)) {
        event.preventDefault()
        turnPage(-1)
    }
}

// keep the screen on while the sheet is up; needs a secure context
// (localhost or the tailnet HTTPS address), and quietly does nothing otherwise
let wakeLock: WakeLockSentinel | null = null
async function holdWakeLock() {
    try {
        wakeLock = (await navigator.wakeLock?.request('screen')) ?? null
    } catch {
        wakeLock = null
    }
}
function onVisibility() {
    if (document.visibilityState === 'visible') holdWakeLock()
}

onMounted(() => {
    load()
    holdWakeLock()
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('keydown', onKey)
    window.addEventListener('resize', fitColumns)
    window.addEventListener('orientationchange', fitColumns)
})
onBeforeUnmount(() => {
    wakeLock?.release().catch(() => {})
    document.removeEventListener('visibilitychange', onVisibility)
    window.removeEventListener('keydown', onKey)
    window.removeEventListener('resize', fitColumns)
    window.removeEventListener('orientationchange', fitColumns)
    headSize.disconnect()
})
</script>

<style scoped>
.practice-sheet {
    max-width: 900px;
}
.practice-sheet.two-col {
    max-width: none;
}
.practice-sheet.two-col :deep(.song-sheet) {
    column-count: 2;
    column-gap: 3rem;
}
.done-bar {
    position: sticky;
    bottom: 16px;
    z-index: 2;
    display: flex;
    justify-content: center;
    margin-top: 24px;
}
</style>
