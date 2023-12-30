<template>
  <h1>Hello world</h1>
  <DataTableBase v-if="app.performSongs" :headers="headers" :items="app.performSongs" :on-save="onSave" />
  <v-progress-circular indeterminate color="primary" v-else></v-progress-circular>
  <SpotifySaveRecentTracksButton />
  <GCalAuth />
  <p v-if="numSpotifyHistory">Spotify history records: {{ numSpotifyHistory }}</p>
  <div v-if="diaryNote" v-html="md.render(diaryNote.body)"></div>
</template>

<script lang="ts" setup>
import DataTableBase from '@/components/DataTableBase.vue';
import SpotifySaveRecentTracksButton from '@/components/SpotifySaveRecentTracksButton.vue';
import GCalAuth from '@/components/GCalAuth.vue';
import PerformSongEdit from '@/components/PerformSongEdit.vue';
import { computed, nextTick, ref, watchEffect } from 'vue';
import { useAppStore } from '@/store/app';
import markdownit from 'markdown-it'
import Axios from 'axios';
Axios.defaults.baseURL = '/api';
import { readPerformSongsList, PerformSongRead, spotifyHistoryCount, joplinGetNoteId, joplinGetNote, JoplinNote } from '@/api';
import { onMounted } from 'vue';
const headers = ref([
  { title: 'id', key: 'id' },
  { title: 'name', key: 'name' },
  { title: 'artist_name', key: 'artist_name' },
  { title: 'learned', key: 'learned' },
])
// const performSongs = ref<PerformSongRead[]>();
const app = useAppStore()
const md = markdownit()
const performSongsLoading = ref(false);
const numSpotifyHistory = ref<Number>()
const joplinNoteId = ref<string>()
const diaryNote = ref<JoplinNote>()
onMounted(async () => {
  await app.loadPerformSongs()
  console.log('loadPerformSongs() finished')
  // performSongsLoading.value = true;
  // performSongs.value = await readPerformSongsList({ limit: 5000 })
  //   .then((res) => {
  //     performSongsLoading.value = false;
  //     return res.data.sort((a, b) => a.name.localeCompare(b.name));
  //   });
  numSpotifyHistory.value = await spotifyHistoryCount().then((res) => res.data)
  joplinNoteId.value = (await joplinGetNoteId('2023-12-12')).data
});
watchEffect(async () => {
  // console.log(app.performSongs.value);
});
watchEffect(async () => {
  if (joplinNoteId.value) {
    console.log(joplinNoteId.value)
    diaryNote.value = (await joplinGetNote(joplinNoteId.value)).data
    console.log(diaryNote.value)
  }
})
function onSave() {
  // if (editedIndex.value > -1) {
  //   Object.assign(desserts.value[editedIndex.value], editedItem.value)
  // } else {
  //   desserts.value.push(editedItem.value)
  // }
  console.log("onSave()")
}
</script>
