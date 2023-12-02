<template>
<v-row justify="start">
<v-col cols="2">
  <v-btn @click="$router.push(`/performSongs/${randomPerformSong()}`)">
    Random song
  </v-btn>
</v-col>
<v-col>
  <v-switch v-model="includeUnlearned" label="Include unlearned" color="primary"/>
</v-col>
</v-row>
</template>

<script lang="ts" setup>
import { PerformSongRead } from '@/api';
import { ref } from 'vue';

const props = defineProps<{
  items: PerformSongRead[];
  currentId?: number;
}>();
const includeUnlearned = ref(false)
function randomPerformSong() {
  let songs = props.items
  if (includeUnlearned.value === false) {
    songs = songs.filter((song) => song.learned === true)
  }
  songs = songs.filter((song) => song.id !== props.currentId)
  const randomSong = songs[Math.floor(Math.random() * songs.length)];
  return randomSong.id;
}
</script>