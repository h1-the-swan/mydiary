<template>
    <h1>MyDiaryDay</h1>
    <div class="w-75" style="width: auto">
        <my-diary-day-date-picker />
    </div>
    <div>
        <g-cal-auth />
    </div>
    <v-btn v-if="!diaryNoteExists" @click="fetchInitMarkdown">
        get init markdown
    </v-btn>
    <v-dialog v-model="dialog" max-width="900">
        <v-card title="Initialize New Joplin Note">
            <v-form>
                <v-card-text>
                    <div
                        v-if="initMarkdown"
                        style="white-space: pre-wrap"
                        v-html="md.render(initMarkdown)"
                    ></div>
                    <div v-else>
                        initMarkdown Loading...
                        <v-progress-linear indeterminate v-if="!initMarkdown" />
                    </div>
                </v-card-text>
                <v-card-actions>
                    <v-btn
                        color="primary"
                        variant="elevated"
                        @click="onSaveNote"
                        text="Initialize note"
                    ></v-btn>
                    <v-btn text="Close" @click="dialog = false"></v-btn>
                </v-card-actions>
            </v-form>
        </v-card>
    </v-dialog>
    <v-snackbar v-model="snackbarInit">
        Note initialized for date {{ getDateStr }}. ID: {{ joplinNoteId }}
        <template v-slot:actions>
            <v-btn color="green" variant="text" @click="snackbarInit = false">
                Close
            </v-btn>
        </template>
    </v-snackbar>
    <p>Joplin note ID: {{ joplinNoteId }}</p>
    <v-expansion-panels v-if="diaryNoteExists" style="max-width: 800px">
        <v-expansion-panel>
            <v-expansion-panel-title>
                <span v-if="diaryNote">diaryNote</span>
                <span v-else>
                    diaryNote Loading...
                    <v-progress-linear indeterminate v-if="!diaryNote" />
                </span>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
                <div
                    style="white-space: pre-wrap"
                    v-if="diaryNote && diaryNote.body"
                    v-html="md.render(diaryNote.body)"
                ></div>
            </v-expansion-panel-text>
        </v-expansion-panel>
    </v-expansion-panels>
    <nextcloud-thumbnails :dt="getDateStr" :joplin-note-id="joplinNoteId" />
</template>

<script setup lang="ts">
import {
    onMounted,
    computed,
    ref,
    watch,
    watchEffect,
    useTemplateRef,
} from 'vue'
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
// import JoplinSyncButton from '@/components/JoplinSyncButton.vue'
import NextcloudThumbnails from '@/components/NextcloudThumbnails.vue'
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
// const datePicker = useTemplateRef('datePicker')
const getDate = computed(() => {
    const qd = route.query.dt
    if (!qd || qd === 'yesterday') {
        let dt = new Date()
        dt.setDate(dt.getDate() - 1)
        return dt
    } else if (qd === 'today') {
        return new Date()
    } else {
        return new Date(`${route.query.dt as string}T00:00`)
    }
})
const getDateStr = computed(() => {
    return getDate.value.toISOString().split('T')[0]
})
const diaryNoteExists = computed<boolean>(() => {
    return !!joplinNoteId.value && joplinNoteId.value !== 'does_not_exist'
})
function updateDate(val: any) {
    const newQD = val.toISOString().split('T')[0]
    router.push({ query: { dt: newQD } })
}
async function fetchInitMarkdown() {
    dialog.value = true
    initMarkdown.value = ''
    initMarkdown.value = // await axios.get(
        //     `/day_init_markdown/${getDateStr.value}?tz=${
        //         Intl.DateTimeFormat().resolvedOptions().timeZone // TODO: get the timezone of the diary day
        //     }`
        // )
        (
            await axios.get(`/day_init_markdown/${getDateStr.value}?tz=infer`)
        ).data
}
async function onSaveNote() {
    joplinNoteId.value = (
        await joplinInitNote(getDateStr.value, { body: initMarkdown.value })
    ).data
    dialog.value = false
    snackbarInit.value = true
    // datePicker.value?.calendarLoadJoplinInfo()
    app.calendarShouldUpdate = true
}
async function fetchJoplinNoteId() {
    joplinNoteId.value = ''
    console.log('fetchJoplinNoteId()')
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
// watch(getDate, fetchInitMarkdown, { immediate: true })
watch(getDate, fetchJoplinNoteId, { immediate: true })
watch(joplinNoteId, fetchJoplinNote, { immediate: true })
watch(joplinNoteId, () => console.log(joplinNoteId.value))
watch(joplinNoteId, fetchJoplinNoteImages, { immediate: true })
watchEffect(() => console.log(diaryNote.value))
watchEffect(() => console.log(diaryNoteImages.value))
</script>
