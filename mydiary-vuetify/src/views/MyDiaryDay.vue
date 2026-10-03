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
                <v-btn v-if="diaryNoteExists" size="small" @click="gcalRefreshOpen = true">
                    Refresh calendar events
                </v-btn>
                <v-btn v-if="!diaryNoteExists" size="small" @click="openCreateDialog">
                    Create note for this day
                </v-btn>
            </div>
        </div>

        <div v-if="diaryNoteExists" class="reading mb-8">
            <section-header label="Diary note" />
            <tag-chips
                class="mb-4"
                target-type="day"
                :target-id="getDateStr"
                :reload-key="diaryNote?.id"
                editable
            />
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
                            v-router-links
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

        <v-dialog v-model="dialog" max-width="900" :persistent="creating">
            <v-card :title="`Create note for ${createLabel}`">
                <v-card-text>
                    <v-alert
                        v-for="failure in syncFailures"
                        :key="failure.source"
                        class="mb-3"
                        type="warning"
                        variant="tonal"
                        density="compact"
                    >
                        Couldn't sync {{ failure.source }} ({{ failure.error }}).
                        The preview shows what was already saved.
                    </v-alert>
                    <v-alert
                        v-if="previewError"
                        class="mb-3"
                        type="error"
                        variant="tonal"
                        density="compact"
                    >
                        {{ previewError }}
                    </v-alert>
                    <v-alert
                        v-if="createError"
                        class="mb-3"
                        type="error"
                        variant="tonal"
                        density="compact"
                    >
                        Creating the note failed ({{ createError }}).
                    </v-alert>
                    <div v-if="syncing">
                        Syncing the day's sources…
                        <v-progress-linear indeterminate />
                    </div>
                    <div
                        v-else-if="initMarkdown"
                        class="prose"
                        v-html="md.render(initMarkdown)"
                    ></div>
                    <div v-else-if="!previewError">
                        Loading the preview…
                        <v-progress-linear indeterminate />
                    </div>
                </v-card-text>
                <v-card-actions>
                    <v-btn
                        color="primary"
                        variant="elevated"
                        text="Create note"
                        :disabled="!initMarkdown"
                        :loading="creating"
                        @click="onSaveNote"
                    ></v-btn>
                    <!-- a create can't be called back, so the dialog stays
                         open to show how it went -->
                    <v-btn
                        text="Cancel"
                        :disabled="creating"
                        @click="dialog = false"
                    ></v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

        <gcal-refresh-dialog
            v-if="gcalRefreshOpen"
            :dt="getDateStr"
            @close="gcalRefreshOpen = false"
            @refreshed="onGcalRefreshed"
        />

        <v-snackbar v-model="snackbarGcalRefresh">
            Calendar events refreshed for {{ gcalRefreshedLabel }}.
            <template v-slot:actions>
                <v-btn variant="text" @click="snackbarGcalRefresh = false">Close</v-btn>
            </template>
        </v-snackbar>

        <v-snackbar v-model="snackbarInit">
            Note created for {{ createLabel }}.
            <template v-slot:actions>
                <v-btn variant="text" @click="snackbarInit = false">Close</v-btn>
            </template>
        </v-snackbar>
    </page-shell>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { md } from '@/markdown'
import {
    dayNewNotePreview,
    daySyncSources,
    joplinGetNote,
    joplinGetNoteId,
    JoplinNote,
    joplinNoteImages,
    MyDiaryImageRead,
    joplinInitNote,
    SourceStatusRead,
} from '@/api'
import GCalAuth from '@/components/GCalAuth.vue'
import GcalRefreshDialog from '@/components/GcalRefreshDialog.vue'
import MyDiaryDayDatePicker from '@/components/MyDiaryDayDatePicker.vue'
import PageShell from '@/components/PageShell.vue'
import SectionHeader from '@/components/SectionHeader.vue'
// import JoplinSyncButton from '@/components/JoplinSyncButton.vue'
import PhotosSection from '@/components/PhotosSection.vue'
import MapSection from '@/components/MapSection.vue'
import TagChips from '@/components/TagChips.vue'
import { useAppStore } from '@/store/app'
import { detailOf, useDiaryDate, toDateStr } from '@/util'
axios.defaults.baseURL = '/api'
const router = useRouter()
const app = useAppStore()
const initMarkdown = ref('')
// the day the create dialog opened on, so its preview and Create can't land
// on different days; `openCount` drops responses from an earlier opening
const createDt = ref('')
const createLabel = ref('')
let openCount = 0
const syncing = ref(false)
const syncFailures = ref<SourceStatusRead[]>([])
const previewError = ref('')
const creating = ref(false)
const createError = ref('')
const joplinNoteId = ref('')
const diaryNote = ref<JoplinNote>()
const diaryNoteImages = ref<MyDiaryImageRead[]>([])
const dialog = ref(false)
const snackbarInit = ref(false)
const gcalRefreshOpen = ref(false)
const snackbarGcalRefresh = ref(false)
// the refreshed day, kept so the snackbar doesn't follow a day change
const gcalRefreshedLabel = ref('')
const getDate = useDiaryDate()
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
// Source Sync first, then the preview, which reads what the sync saved. A
// Source that fails is a warning: the preview still shows the rest.
async function openCreateDialog() {
    const dt = getDateStr.value
    const opening = ++openCount
    createDt.value = dt
    createLabel.value = dateLabel.value
    dialog.value = true
    initMarkdown.value = ''
    syncFailures.value = []
    previewError.value = ''
    createError.value = ''
    syncing.value = true
    try {
        const report = (await daySyncSources(dt)).data
        if (opening !== openCount) return
        syncFailures.value = report.statuses.filter((s) => !s.ok)
    } catch (e) {
        if (opening !== openCount) return
        syncFailures.value = [
            { source: 'the sources', ok: false, error: detailOf(e) },
        ]
    }
    syncing.value = false
    try {
        const preview = (await dayNewNotePreview(dt)).data
        if (opening !== openCount) return
        initMarkdown.value = preview
    } catch (e) {
        if (opening !== openCount) return
        previewError.value = `Couldn't load the preview (${detailOf(e)}).`
    }
}
// the server builds the note from the database, as the preview did
async function onSaveNote() {
    creating.value = true
    createError.value = ''
    const dt = createDt.value
    try {
        const noteId = (await joplinInitNote(dt)).data
        // the page may have moved to another day meanwhile
        if (getDateStr.value === dt) joplinNoteId.value = noteId
    } catch (e) {
        createError.value = detailOf(e)
        return
    } finally {
        creating.value = false
    }
    dialog.value = false
    snackbarInit.value = true
    app.calendarShouldUpdate = true
}
async function onGcalRefreshed() {
    gcalRefreshOpen.value = false
    gcalRefreshedLabel.value = dateLabel.value
    snackbarGcalRefresh.value = true
    await fetchJoplinNote()
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
// the dialog belongs to the day it opened on (back/forward can change the day)
watch(getDateStr, () => {
    if (!creating.value) dialog.value = false
})
watch(joplinNoteId, fetchJoplinNote, { immediate: true })
watch(joplinNoteId, fetchJoplinNoteImages, { immediate: true })
</script>
