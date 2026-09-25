<template>
    <v-dialog :model-value="true" max-width="960" scrollable @update:model-value="emit('close')">
        <v-card>
            <v-card-title>New {{ INSTRUMENT_LABELS[instrument].toLowerCase() }} sheet</v-card-title>
            <v-card-text>
                <v-radio-group v-model="mode" inline hide-details class="mb-4">
                    <v-radio label="Paste a tab" value="paste" />
                    <v-radio label="Lyrics from LRCLIB" value="lrclib" />
                    <v-radio v-if="sources.length" :label="`Copy the ${INSTRUMENT_LABELS[sources[0].instrument].toLowerCase()} sheet`" value="copy" />
                    <v-radio label="Blank" value="blank" />
                </v-radio-group>

                <div class="d-flex flex-wrap ga-3 mb-4">
                    <v-text-field v-model="key" label="Sounds in" hide-details class="key-field" />
                    <v-text-field v-model.number="capo" label="Capo" type="number" min="0" hide-details class="key-field" />
                    <span class="align-self-center text-body-2 text-medium-emphasis">{{ describeKey(key, capo) }}</span>
                </div>

                <v-textarea
                    v-if="mode === 'paste'"
                    v-model="pasteText"
                    label="Chords over lyrics, as copied from a tab site"
                    rows="10"
                    class="mono"
                />
                <div v-else-if="mode === 'lrclib'" class="mb-4">
                    <v-btn :loading="fetching" prepend-icon="mdi-download" @click="fetchLyrics">
                        Fetch lyrics
                    </v-btn>
                    <span v-if="lrclibMessage" class="ml-3 text-body-2">{{ lrclibMessage }}</span>
                </div>
                <v-textarea
                    v-else-if="mode === 'blank'"
                    v-model="blankText"
                    label="Sheet (ChordPro)"
                    rows="10"
                    class="mono"
                />

                <v-alert v-if="nonChords.length" type="warning" variant="tonal" density="compact" class="mb-4">
                    These brackets will show as chords: {{ nonChords.map((t) => `[${t}]`).join(', ') }}.
                    Change them to parentheses after creating the sheet.
                </v-alert>

                <div v-if="draft.trim()" class="preview pa-3">
                    <SongSheet :parsed="parseSheet(draft)" show-all />
                </div>
            </v-card-text>
            <v-card-actions>
                <v-spacer />
                <v-btn variant="text" @click="emit('close')">Cancel</v-btn>
                <v-btn color="primary" variant="flat" :loading="creating" @click="create">Create</v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { isAxiosError } from 'axios'
import SongSheet from '@/components/SongSheet.vue'
import {
    bracketedNonChords,
    convertChordsOverLyrics,
    copySheet,
    describeKey,
    parseSheet,
    suggestSections,
} from '@/chordpro'
import type { Instrument } from '@/chords'
import { INSTRUMENT_LABELS, capoOrNull } from '@/practice'
import {
    PerformSongRead,
    SongArrangementRead,
    createSongArrangement,
    lookupLrclibLyrics,
} from '@/api'

const props = defineProps<{
    performSong: PerformSongRead
    instrument: Instrument
    arrangements: SongArrangementRead[]
}>()
const emit = defineEmits<{ close: []; created: [a: SongArrangementRead] }>()

type Mode = 'paste' | 'lrclib' | 'copy' | 'blank'
const sources = computed(() => props.arrangements.filter((a) => a.instrument !== props.instrument))
const mode = ref<Mode>(sources.value.length ? 'copy' : 'paste')

// a guitar sheet starts from the song's own key and capo, which have always been
// the guitar's; another instrument starts in the key the song already sounds in
const key = ref<string>(
    (props.instrument === 'guitar' ? props.performSong.key : sources.value[0]?.key ?? props.performSong.key) ?? ''
)
const capo = ref<number | null>(props.instrument === 'guitar' ? props.performSong.capo ?? null : 0)

const pasteText = ref('')
const blankText = ref(props.performSong.lyrics ?? '')
const fetched = ref('')
const fetching = ref(false)
const lrclibMessage = ref('')
const creating = ref(false)

const draft = computed(() => {
    switch (mode.value) {
        case 'paste':
            return pasteText.value.trim() ? convertChordsOverLyrics(pasteText.value) : ''
        case 'lrclib':
            return fetched.value ? suggestSections(fetched.value) : ''
        case 'copy': {
            const src = sources.value[0]
            return src ? copySheet(src.sheet ?? '', src, { key: key.value, capo: capo.value }) : ''
        }
        default:
            return blankText.value
    }
})
const nonChords = computed(() => bracketedNonChords(draft.value))

async function fetchLyrics() {
    fetching.value = true
    lrclibMessage.value = ''
    try {
        const found = (await lookupLrclibLyrics(props.performSong.id)).data
        fetched.value = found.plain_lyrics
        lrclibMessage.value = `Found “${found.track_name}” by ${found.artist_name}. Check the suggested sections.`
    } catch (e) {
        fetched.value = ''
        lrclibMessage.value =
            isAxiosError(e) && e.response?.status === 404
                ? 'LRCLIB has no lyrics for this song.'
                : "LRCLIB couldn't be reached. Try again later."
    } finally {
        fetching.value = false
    }
}

async function create() {
    creating.value = true
    try {
        const source =
            mode.value === 'copy' ? `copied:${sources.value[0].id}` : mode.value === 'blank' ? 'manual' : mode.value
        const created = (
            await createSongArrangement(props.performSong.id, {
                instrument: props.instrument,
                key: key.value || null,
                capo: capoOrNull(capo.value),
                sheet: draft.value,
                source,
            })
        ).data
        emit('created', created)
    } finally {
        creating.value = false
    }
}
</script>

<style scoped>
.key-field {
    max-width: 130px;
}
.mono :deep(textarea) {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.9rem;
}
.preview {
    max-height: 50vh;
    overflow-y: auto;
    border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    border-radius: 8px;
}
</style>
