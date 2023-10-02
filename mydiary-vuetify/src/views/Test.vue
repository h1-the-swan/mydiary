<template>
  <h1>Hello world</h1>
  <v-progress-circular indeterminate color="primary" v-if="performSongsLoading"></v-progress-circular>
  <DataTableBase v-if="performSongs" :headers="headers" :items="performSongs" :on-save="onSave" />
  <SpotifySaveRecentTracksButton />
  <GCalAuth />
</template>

<script lang="ts" setup>
import DataTableBase from '@/components/DataTableBase.vue';
import SpotifySaveRecentTracksButton from '@/components/SpotifySaveRecentTracksButton.vue';
import GCalAuth from '@/components/GCalAuth.vue';
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
const performSongsLoading = ref(false);
onMounted(async () => {
  performSongsLoading.value = true;
  performSongs.value = await readPerformSongsList({ limit: 5000 })
    .then((res) => {
      performSongsLoading.value = false;
      return res.data.sort((a, b) => a.name.localeCompare(b.name));
    });
});
watchEffect(async () => {
  console.log(performSongs.value);
});
function onSave() {
  // if (editedIndex.value > -1) {
  //   Object.assign(desserts.value[editedIndex.value], editedItem.value)
  // } else {
  //   desserts.value.push(editedItem.value)
  // }
  console.log("onSave()")
}
</script>
