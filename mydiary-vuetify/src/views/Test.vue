<template>
  <h1>Hello world</h1>
  <DataTableBase v-if="performSongs" :headers="headers" :items="performSongs" />
  <SpotifySaveRecentTracksButton />
</template>

<script lang="ts" setup>
import DataTableBase from '@/components/DataTableBase.vue';
import SpotifySaveRecentTracksButton from '@/components/SpotifySaveRecentTracksButton.vue';
import { computed, nextTick, ref, watchEffect } from 'vue';
import Axios from 'axios';
Axios.defaults.baseURL = '/api';
import { readPerformSongsList, PerformSongRead } from '@/api';
import { onMounted } from 'vue';
const headers = ref([
  { title: 'id', key: 'id' },
  { title: 'name', key: 'name' },
  { title: 'artist_name', key: 'artist_name' },
  { title: 'learned', key: 'learned' },
])
const performSongs = ref<PerformSongRead[]>();
onMounted(async () => {
  performSongs.value = await readPerformSongsList({ limit: 5000 }).then((res) => res.data.sort((a, b) => a.name.localeCompare(b.name)));
});
watchEffect(async () => {
  console.log(performSongs.value);
});
</script>
