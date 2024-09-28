<template>
    <h1>Test Day</h1>
    <div class="w-75" style="width: auto">
        <DatePicker
            ref="calendar"
            :model-value="getDate"
            @update:model-value="updateDate"
            :attributes="attributes"
            expanded
        />
    </div>
    <g-cal-auth />
    <v-btn @click="fetchInitMarkdown">get init markdown</v-btn>
    <v-expansion-panels style="max-width: 800px">
        <v-expansion-panel>
            <v-expansion-panel-title>
                <span v-if="initMarkdown">initMarkdown</span>
                <span v-else>
                    initMarkdown Loading...
                    <v-progress-linear indeterminate v-if="!initMarkdown" />
                </span>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
                <div
                    style="white-space: pre"
                    v-html="md.render(initMarkdown)"
                ></div>
            </v-expansion-panel-text>
        </v-expansion-panel>
    </v-expansion-panels>
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
                    style="white-space: pre"
                    v-if="diaryNote"
                    v-html="md.render(diaryNote.body)"
                ></div>
            </v-expansion-panel-text>
        </v-expansion-panel>
    </v-expansion-panels>
    <nextcloud-thumbnails :dt="getDateStr" :joplin-note-id="joplinNoteId" />
</template>

<script setup lang="ts">
import { onMounted, computed, ref, watch, watchEffect } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'
import markdownit from 'markdown-it'
import { DatePicker } from 'v-calendar'
import 'v-calendar/style.css'
import {
    joplinGetNote,
    joplinGetNoteId,
    JoplinNote,
    joplinNoteImages,
    MyDiaryImageRead,
} from '@/api'
import GCalAuth from '@/components/GCalAuth.vue'
// import JoplinSyncButton from '@/components/JoplinSyncButton.vue'
import NextcloudThumbnails from '@/components/NextcloudThumbnails.vue'
import { useAppStore } from '@/store/app'
import { AttributeConfig } from 'v-calendar/dist/types/src/utils/attribute'
axios.defaults.baseURL = '/api'
const router = useRouter()
const route = useRoute()
const app = useAppStore()
const calendar = ref<any>(null)
const calendarVisibleDates = computed<Date[]>(() => {
    if (calendar.value == null) {
        return []
    }
    return calendar.value.calendarRef.days.map((d: any) => d.date)
})
const joplinInfoAllDays = ref<any[]>([])
const initMarkdown = ref('')
const md = markdownit()
const joplinNoteId = ref('')
const diaryNote = ref<JoplinNote>()
const diaryNoteImages = ref<MyDiaryImageRead[]>([])
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
    initMarkdown.value = ''
    initMarkdown.value = (
        // await axios.get(
        //     `/day_init_markdown/${getDateStr.value}?tz=${
        //         Intl.DateTimeFormat().resolvedOptions().timeZone // TODO: get the timezone of the diary day
        //     }`
        // )
        await axios.get(
            `/day_init_markdown/${getDateStr.value}?tz=infer`
        )
    ).data
}
async function fetchJoplinNoteId() {
    joplinNoteId.value = ''
    console.log('fetchJoplinNoteId()')
    joplinNoteId.value = (await joplinGetNoteId(getDateStr.value)).data
}
async function fetchJoplinNote() {
    diaryNote.value = undefined
    if (diaryNoteExists.value) {
        diaryNote.value = (await joplinGetNote(joplinNoteId.value)).data
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
const attributes = computed<AttributeConfig[]>(() => [
    {
        highlight: {
            fillMode: 'outline',
            style: { 'border-width': '1px', 'border-style': 'dashed' },
        },
        dates: joplinInfoAllDays.value.map(
            (item: any) => new Date(`${item.title}T00:00`)
        ),
    },
    {
        dot: 'blue',
        dates: joplinInfoAllDays.value
            .filter((item: any) => item.has_words)
            .map((item: any) => new Date(`${item.title}T00:00`)),
    },
    {
        dot: 'orange',
        dates: joplinInfoAllDays.value
            .filter((item: any) => item.has_images)
            .map((item: any) => new Date(`${item.title}T00:00`)),
    },
])
watch(getDate, fetchInitMarkdown, { immediate: true })
watch(getDate, fetchJoplinNoteId, { immediate: true })
watch(joplinNoteId, fetchJoplinNote, { immediate: true })
watch(joplinNoteId, () => console.log(joplinNoteId.value))
watch(joplinNoteId, fetchJoplinNoteImages, { immediate: true })
watchEffect(() => {
    if (!calendarVisibleDates.value.length) return
    const sortedDates = calendarVisibleDates.value.sort((a: any, b: any) => a - b)
    const minDt = sortedDates[0].toISOString().split('T')[0]
    const maxDt = sortedDates[sortedDates.length - 1]
        .toISOString()
        .split('T')[0]
    app.loadJoplinInfoAllDays(minDt, maxDt)
})
watchEffect(() => (joplinInfoAllDays.value = app.joplinInfoAllDays))
watchEffect(() => console.log(joplinInfoAllDays))
watchEffect(() => console.log(diaryNote.value))
watchEffect(() => console.log(diaryNoteImages.value))
</script>
