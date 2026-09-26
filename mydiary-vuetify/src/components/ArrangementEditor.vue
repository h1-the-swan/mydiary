<template>
    <div>
        <div class="d-flex flex-wrap align-center ga-3 mb-4">
            <v-text-field v-model="key" label="Sounds in" hide-details class="key-field" />
            <v-text-field
                v-model.number="capo"
                label="Capo"
                type="number"
                min="0"
                hide-details
                class="key-field"
            />
            <span class="text-body-2 text-medium-emphasis">{{ describeKey(key, capo) }}</span>
            <v-spacer />
            <v-btn variant="text" color="error" @click="remove">Delete</v-btn>
            <v-btn color="primary" variant="flat" :disabled="!dirty" :loading="saving" @click="save">
                Save
            </v-btn>
        </div>

        <v-alert
            v-if="nonChords.length"
            type="warning"
            variant="tonal"
            density="compact"
            class="mb-4"
        >
            These brackets will show as chords: {{ nonChords.map((t) => `[${t}]`).join(', ') }}.
            Use parentheses for alternate lyrics.
        </v-alert>

        <v-btn-toggle v-if="narrow" v-model="pane" mandatory density="compact" class="mb-3">
            <v-btn value="edit">Edit</v-btn>
            <v-btn value="preview">Preview</v-btn>
        </v-btn-toggle>
        <div class="d-flex ga-4">
            <v-textarea
                v-show="!narrow || pane === 'edit'"
                v-model="sheet"
                class="sheet-editor flex-1-1"
                label="Sheet (ChordPro)"
                auto-grow
                rows="20"
                spellcheck="false"
            />
            <div v-show="!narrow || pane === 'preview'" class="flex-1-1 sheet-preview">
                <SongSheet :parsed="parsed" show-all />
            </div>
        </div>

        <div class="mt-6">
            <section-header label="Chords" :meta="`${parsed.chords.length}`" />
        </div>
        <ChordPanel :sheet="sheet" :instrument="arrangement.instrument as Instrument" @update:sheet="sheet = $event" />

        <v-dialog v-model="renameDialog" max-width="560">
            <v-card>
                <v-card-title>Keep practice history?</v-card-title>
                <v-card-text>
                    <p class="mb-4">
                        These sections have practice history but aren't in any sheet any
                        more. Move each one's history to a section that is, or leave it as
                        it is.
                    </p>
                    <v-select
                        v-for="r in renames"
                        :key="r.from"
                        v-model="r.to"
                        :label="`History for “${r.from}”`"
                        :items="[{ title: 'Leave it', value: null }, ...newKeys.map((k) => ({ title: k, value: k }))]"
                        class="mb-2"
                    />
                </v-card-text>
                <v-card-actions>
                    <v-spacer />
                    <v-btn variant="text" @click="renameDialog = false">Cancel</v-btn>
                    <v-btn color="primary" variant="flat" @click="confirmRenames">Save</v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDisplay } from 'vuetify'
import ChordPanel from '@/components/ChordPanel.vue'
import SectionHeader from '@/components/SectionHeader.vue'
import SongSheet from '@/components/SongSheet.vue'
import { bracketedNonChords, describeKey, parseSheet, sectionKeys } from '@/chordpro'
import type { Instrument } from '@/chords'
import { capoOrNull } from '@/practice'
import {
    SongArrangementRead,
    deleteSongArrangement,
    readSectionLevels,
    renamePracticeSection,
    updateSongArrangement,
} from '@/api'

const props = defineProps<{
    arrangement: SongArrangementRead
    /** The song's other arrangements' sheets: their sections still count as in use. */
    otherSheets: string[]
}>()
const emit = defineEmits<{ saved: [a: SongArrangementRead]; deleted: [] }>()

const { smAndDown: narrow } = useDisplay()
const pane = ref<'edit' | 'preview'>('edit')
const sheet = ref(props.arrangement.sheet ?? '')
const key = ref(props.arrangement.key ?? '')
const capo = ref<number | null>(props.arrangement.capo ?? null)
const saving = ref(false)

const parsed = computed(() => parseSheet(sheet.value))
const newKeys = computed(() => sectionKeys(parsed.value))
const nonChords = computed(() => bracketedNonChords(sheet.value))
const dirty = computed(
    () =>
        sheet.value !== (props.arrangement.sheet ?? '') ||
        (key.value || null) !== (props.arrangement.key ?? null) ||
        capoOrNull(capo.value) !== (props.arrangement.capo ?? null)
)

const renameDialog = ref(false)
const renames = ref<{ from: string; to: string | null }[]>([])

async function save() {
    // warn only about sections this edit removed: comparing against the saved
    // sheet means a history left behind once isn't raised again on every save
    const history = new Set(
        (await readSectionLevels(props.arrangement.perform_song_id)).data.map((l) => l.section_key)
    )
    const inUse = new Set([...newKeys.value, ...props.otherSheets.flatMap((s) => sectionKeys(parseSheet(s)))])
    const orphaned = sectionKeys(parseSheet(props.arrangement.sheet ?? '')).filter(
        (k) => history.has(k) && !inUse.has(k)
    )
    if (orphaned.length) {
        renames.value = orphaned.map((from) => ({ from, to: null }))
        renameDialog.value = true
        return
    }
    await persist()
}

async function confirmRenames() {
    for (const r of renames.value) {
        if (r.to) {
            await renamePracticeSection(props.arrangement.perform_song_id, { from_key: r.from, to_key: r.to })
        }
    }
    renameDialog.value = false
    await persist()
}

async function persist() {
    saving.value = true
    try {
        const saved = (
            await updateSongArrangement(props.arrangement.id, {
                sheet: sheet.value,
                key: key.value || null,
                capo: capoOrNull(capo.value),
            })
        ).data
        emit('saved', saved)
    } finally {
        saving.value = false
    }
}

async function remove() {
    if (!window.confirm(`Delete the ${props.arrangement.instrument} sheet? Practice history is kept.`)) return
    await deleteSongArrangement(props.arrangement.id)
    emit('deleted')
}

defineExpose({ dirty })
</script>

<style scoped>
.key-field {
    max-width: 130px;
}
.sheet-editor :deep(textarea) {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.9rem;
}
.sheet-preview {
    min-width: 0;
}
</style>
