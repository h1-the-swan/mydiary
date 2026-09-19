<template>
    <div>
        <p v-if="!parsed.chords.length" class="text-body-2 text-medium-emphasis">
            No chords in the sheet yet.
        </p>
        <div class="d-flex flex-wrap ga-4">
            <v-card v-for="chord in parsed.chords" :key="chord" border class="chord-card pa-3">
                <div class="d-flex justify-center">
                    <ChordDiagram
                        :chord="chord"
                        :instrument="instrument"
                        :define="parsed.defines[chord]"
                        :size="110"
                    />
                </div>
                <div class="d-flex flex-wrap align-center ga-1 my-2">
                    <v-btn
                        v-for="(_, i) in positions(chord).slice(0, 4)"
                        :key="i"
                        size="x-small"
                        :variant="matchesPosition(chord, i) ? 'flat' : 'tonal'"
                        :color="matchesPosition(chord, i) ? 'primary' : undefined"
                        @click="usePosition(chord, i)"
                    >
                        {{ i + 1 }}
                    </v-btn>
                    <v-btn
                        v-if="parsed.defines[chord]"
                        size="x-small"
                        variant="text"
                        @click="emit('update:sheet', setChordDefine(sheet, chord, null))"
                    >
                        Default
                    </v-btn>
                </div>
                <v-text-field
                    :model-value="fretDrafts[chord] ?? ''"
                    :label="`Frets (e.g. ${instrument === 'guitar' ? 'x32010' : '0003'})`"
                    :error-messages="fretErrors[chord]"
                    density="compact"
                    hide-details="auto"
                    class="mb-2"
                    @update:model-value="fretDrafts[chord] = $event"
                    @keydown.enter="applyFrets(chord)"
                    @blur="applyFrets(chord)"
                />
                <v-text-field
                    :model-value="parsed.chordNotes[chord] ?? ''"
                    label="Note"
                    density="compact"
                    hide-details
                    @change="emit('update:sheet', setChordNote(sheet, chord, ($event.target as HTMLInputElement).value))"
                />
            </v-card>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import ChordDiagram from '@/components/ChordDiagram.vue'
import {
    defineFromAbsoluteFrets,
    parseFretString,
    parseSheet,
    setChordDefine,
    setChordNote,
} from '@/chordpro'
import {
    STRINGS,
    defineFromFingering,
    loadChordDb,
    lookupChord,
    type ChordDb,
    type Fingering,
    type Instrument,
} from '@/chords'

const props = defineProps<{ sheet: string; instrument: Instrument }>()
const emit = defineEmits<{ 'update:sheet': [sheet: string] }>()

const parsed = computed(() => parseSheet(props.sheet))
const db = ref<ChordDb>()
const fretDrafts = reactive<Record<string, string>>({})
const fretErrors = reactive<Record<string, string>>({})

watch(
    () => props.instrument,
    async (instrument) => {
        db.value = await loadChordDb(instrument)
    },
    { immediate: true }
)

function positions(chord: string): Fingering[] {
    return db.value ? lookupChord(db.value, chord) : []
}

function matchesPosition(chord: string, i: number): boolean {
    const d = parsed.value.defines[chord]
    const p = positions(chord)[i]
    return Boolean(d && p && d.baseFret === p.baseFret && d.frets.join() === p.frets.join())
}

function usePosition(chord: string, i: number) {
    emit('update:sheet', setChordDefine(props.sheet, chord, defineFromFingering(chord, positions(chord)[i])))
}

function applyFrets(chord: string) {
    const draft = (fretDrafts[chord] ?? '').trim()
    if (!draft) return
    const frets = parseFretString(draft, STRINGS[props.instrument])
    if (!frets) {
        fretErrors[chord] = `Needs ${STRINGS[props.instrument]} values: a fret number, 0 or x`
        return
    }
    fretErrors[chord] = ''
    fretDrafts[chord] = ''
    emit('update:sheet', setChordDefine(props.sheet, chord, defineFromAbsoluteFrets(chord, frets)))
}
</script>

<style scoped>
.chord-card {
    width: 200px;
}
</style>
