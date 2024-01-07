<template>
  <h1>Test Day</h1>
  <v-btn @click="console.log(route.query.dt)">check dt</v-btn>
  <v-date-picker :model-value="getDate" @update:model-value="updateDate" />
  <v-btn @click="fetchInitMarkdown">get init markdown</v-btn>
  <v-expansion-panels style="max-width: 800px;">
    <v-expansion-panel>
      <v-expansion-panel-title>
        <span v-if="initMarkdown">initMarkdown</span>
        <span v-else>
          initMarkdown Loading...
          <v-progress-linear indeterminate v-if="!initMarkdown" />
        </span>
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <div style="white-space: pre;" v-html="md.render(initMarkdown)"></div>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
  <p>Joplin note ID: {{ joplinNoteId }}</p>
  <v-expansion-panels v-if="diaryNoteExists" style="max-width: 800px;">
    <v-expansion-panel>
      <v-expansion-panel-title>
        <span v-if="diaryNote">diaryNote</span>
        <span v-else>
          diaryNote Loading...
          <v-progress-linear indeterminate v-if="!diaryNote" />
        </span>
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <div style="white-space: pre;" v-if="diaryNote" v-html="md.render(diaryNote.body)"></div>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>

<script setup lang="ts">
import { onMounted, computed, ref, watch, watchEffect } from 'vue';
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'
import markdownit from 'markdown-it'
import { joplinGetNote, joplinGetNoteId, JoplinNote } from '@/api';
axios.defaults.baseURL = '/api'
const router = useRouter()
const route = useRoute()
const initMarkdown = ref('')
const md = markdownit()
const joplinNoteId = ref('')
const diaryNote = ref<JoplinNote>()
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
  initMarkdown.value = (await axios.get(`/day_init_markdown/${getDateStr.value}`)).data
}
async function fetchJoplinNoteId() {
  joplinNoteId.value = ''
  joplinNoteId.value = (await joplinGetNoteId(getDateStr.value)).data
}
async function fetchJoplinNote() {
  diaryNote.value = undefined
  if (diaryNoteExists.value) {
    diaryNote.value = (await joplinGetNote(joplinNoteId.value)).data
  }
}
watch(getDate, fetchInitMarkdown, { immediate: true })
watch(getDate, fetchJoplinNoteId, { immediate: true })
watch(joplinNoteId, fetchJoplinNote, { immediate: true })
</script>