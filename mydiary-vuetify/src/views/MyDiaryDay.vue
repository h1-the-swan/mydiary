<template>
    <page-shell :eyebrow="weekdayLabel" :title="dateLabel">
        <template #actions>
            <v-btn
                icon="mdi-chevron-left"
                variant="text"
                density="comfortable"
                aria-label="Previous day"
                @click="shiftDay(-1)"
            />
            <v-btn size="small" :disabled="isToday" @click="goToToday">
                Today
            </v-btn>
            <v-btn
                icon="mdi-chevron-right"
                variant="text"
                density="comfortable"
                aria-label="Next day"
                @click="shiftDay(1)"
            />
        </template>

        <div class="reading mb-8">
            <my-diary-day-date-picker />
            <div class="d-flex align-center flex-wrap ga-2 mt-4">
                <g-cal-auth />
                <v-btn v-if="!diaryNoteExists" size="small" @click="fetchInitMarkdown">
                    Create note for this day
                </v-btn>
            </div>
        </div>

        <div v-if="diaryNoteExists" class="reading mb-8">
            <section-header label="Diary note" />
            <v-expansion-panels>
                <v-expansion-panel>
                    <v-expansion-panel-title>
                        <span v-if="diaryNote">{{ diaryNote.title || 'Diary note' }}</span>
                        <span v-else>Loading…</span>
                    </v-expansion-panel-title>
                    <v-expansion-panel-text>
                        <v-progress-linear v-if="!diaryNote" indeterminate />
                        <div
                            v-else-if="diaryNote.body"
                            class="prose"
                            v-html="md.render(diaryNote.body)"
                        ></div>
                        <p v-else class="text-medium-emphasis">
                            This note is empty.
                        </p>
                    </v-expansion-panel-text>
                </v-expansion-panel>
            </v-expansion-panels>
        </div>

        <photos-section
            class="mb-8"
            :dt="getDateStr"
            :joplin-note-id="joplinNoteId"
        />
        <map-section :dt="getDateStr" :joplin-note-id="joplinNoteId" />

        <v-dialog v-model="dialog" max-width="900">
            <v-card title="Create note for this day">
                <v-form>
                    <v-card-text>
                        <div
                            v-if="initMarkdown"
                            class="prose"
                            v-html="md.render(initMarkdown)"
                        ></div>
                        <div v-else>
                            Loading…
                            <v-progress-linear indeterminate />
                        </div>
                    </v-card-text>
                    <v-card-actions>
                        <v-btn
                            color="primary"
                            variant="elevated"
                            text="Create note"
                            @click="onSaveNote"
                        ></v-btn>
                        <v-btn text="Cancel" @click="dialog = false"></v-btn>
                    </v-card-actions>
                </v-form>
            </v-card>
        </v-dialog>

        <v-snackbar v-model="snackbarInit">
            Note created for {{ dateLabel }}.
            <template v-slot:actions>
                <v-btn variant="text" @click="snackbarInit = false">Close</v-btn>
            </template>
        </v-snackbar>
    </page-shell>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'
import markdownit from 'markdown-it'
import {
    joplinGetNote,
    joplinGetNoteId,
    JoplinNote,
    joplinNoteImages,
    MyDiaryImageRead,
    joplinInitNote,
} from '@/api'
import GCalAuth from '@/components/GCalAuth.vue'
import MyDiaryDayDatePicker from '@/components/MyDiaryDayDatePicker.vue'
import PageShell from '@/components/PageShell.vue'
import SectionHeader from '@/components/SectionHeader.vue'
// import JoplinSyncButton from '@/components/JoplinSyncButton.vue'
import PhotosSection from '@/components/PhotosSection.vue'
import MapSection from '@/components/MapSection.vue'
import { useAppStore } from '@/store/app'
axios.defaults.baseURL = '/api'
const router = useRouter()
const route = useRoute()
const app = useAppStore()
const initMarkdown = ref('')
const md = markdownit()
const joplinNoteId = ref('')
const diaryNote = ref<JoplinNote>()
const diaryNoteImages = ref<MyDiaryImageRead[]>([])
const dialog = ref(false)
const snackbarInit = ref(false)
const getDate = computed(() => {
    const qd = route.query.dt
    if (!qd || qd === 'yesterday') {
        const dt = new Date()
        dt.setDate(dt.getDate() - 1)
        return dt
    } else if (qd === 'today') {
        return new Date()
    } else {
        return new Date(`${route.query.dt as string}T00:00`)
    }
})
const getDateStr = computed(() => {
    return toDateStr(getDate.value)
})
const weekdayLabel = computed(() =>
    getDate.value.toLocaleDateString(undefined, { weekday: 'long' })
)
const dateLabel = computed(() =>
    getDate.value.toLocaleDateString(undefined, {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
    })
)
const isToday = computed(() => getDateStr.value === toDateStr(new Date()))
const diaryNoteExists = computed<boolean>(() => {
    return !!joplinNoteId.value && joplinNoteId.value !== 'does_not_exist'
})
function toDateStr(dt: Date) {
    return dt.toISOString().split('T')[0]
}
function updateDate(val: any) {
    const newQD = toDateStr(val)
    router.push({ query: { dt: newQD } })
}
function shiftDay(days: number) {
    const dt = new Date(getDate.value)
    dt.setDate(dt.getDate() + days)
    updateDate(dt)
}
function goToToday() {
    updateDate(new Date())
}
async function fetchInitMarkdown() {
    dialog.value = true
    initMarkdown.value = ''
    initMarkdown.value = (
        await axios.get(`/day_init_markdown/${getDateStr.value}?tz=infer`)
    ).data
}
async function onSaveNote() {
    joplinNoteId.value = (
        await joplinInitNote(getDateStr.value, { body: initMarkdown.value })
    ).data
    dialog.value = false
    snackbarInit.value = true
    app.calendarShouldUpdate = true
}
async function fetchJoplinNoteId() {
    joplinNoteId.value = ''
    joplinNoteId.value = (await joplinGetNoteId(getDateStr.value)).data
}
async function fetchJoplinNote() {
    diaryNote.value = undefined
    if (diaryNoteExists.value) {
        diaryNote.value = (
            await joplinGetNote(joplinNoteId.value, { remove_image_refs: true })
        ).data
    }
}
async function fetchJoplinNoteImages() {
    diaryNoteImages.value = []
    if (diaryNoteExists.value) {
        diaryNoteImages.value = (
            await joplinNoteImages(joplinNoteId.value)
        ).data
    }
}
watch(getDate, fetchJoplinNoteId, { immediate: true })
watch(joplinNoteId, fetchJoplinNote, { immediate: true })
watch(joplinNoteId, fetchJoplinNoteImages, { immediate: true })
</script>
