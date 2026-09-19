<template>
    <section>
        <section-header label="Sheets" :meta="arrangements.map((a) => INSTRUMENT_LABELS[a.instrument]).join(' · ')">
            <template #actions>
                <v-btn
                    v-for="inst in missing"
                    :key="inst"
                    size="small"
                    prepend-icon="mdi-plus"
                    @click="adding = inst"
                >
                    {{ INSTRUMENT_LABELS[inst] }}
                </v-btn>
                <v-btn
                    v-if="arrangements.length"
                    size="small"
                    color="primary"
                    variant="flat"
                    prepend-icon="mdi-play"
                    :to="{ name: 'songPractice', params: { id: performSong.id }, query: { instrument: tab } }"
                >
                    Practice
                </v-btn>
            </template>
        </section-header>

        <p v-if="loaded && !arrangements.length" class="text-body-2 text-medium-emphasis">
            No sheet yet. Add a guitar or ukulele sheet to start practicing.
        </p>
        <template v-else-if="current">
            <v-tabs v-model="tab" density="compact" class="mb-4">
                <v-tab v-for="a in arrangements" :key="a.id" :value="a.instrument">
                    {{ INSTRUMENT_LABELS[a.instrument] }}
                </v-tab>
            </v-tabs>
            <ArrangementEditor
                :key="current.id"
                :arrangement="current"
                :other-sheets="arrangements.filter((a) => a.id !== current!.id).map((a) => a.sheet ?? '')"
                @saved="onSaved"
                @deleted="load"
            />
        </template>

        <NewArrangementDialog
            v-if="adding"
            :perform-song="performSong"
            :instrument="adding"
            :arrangements="arrangements"
            @close="adding = null"
            @created="onCreated"
        />
        <v-snackbar v-model="savedToast" timeout="2000">Sheet saved</v-snackbar>
    </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ArrangementEditor from '@/components/ArrangementEditor.vue'
import NewArrangementDialog from '@/components/NewArrangementDialog.vue'
import SectionHeader from '@/components/SectionHeader.vue'
import type { Instrument } from '@/chords'
import { INSTRUMENTS, INSTRUMENT_LABELS } from '@/practice'
import { PerformSongRead, SongArrangementRead, listSongArrangements } from '@/api'

const props = defineProps<{ performSong: PerformSongRead }>()

const arrangements = ref<SongArrangementRead[]>([])
const loaded = ref(false)
const tab = ref<string>()
const adding = ref<Instrument | null>(null)
const savedToast = ref(false)

const missing = computed(() => INSTRUMENTS.filter((i) => !arrangements.value.some((a) => a.instrument === i)))
const current = computed(() => arrangements.value.find((a) => a.instrument === tab.value))

async function load() {
    arrangements.value = (await listSongArrangements(props.performSong.id)).data
    loaded.value = true
    if (!current.value) tab.value = arrangements.value[0]?.instrument
}

async function onCreated(a: SongArrangementRead) {
    adding.value = null
    await load()
    tab.value = a.instrument
}

function onSaved(a: SongArrangementRead) {
    arrangements.value = arrangements.value.map((x) => (x.id === a.id ? a : x))
    savedToast.value = true
}

watch(() => props.performSong.id, load, { immediate: true })
</script>
