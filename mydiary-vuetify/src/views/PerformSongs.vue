<template>
  <v-container>
    <p>props.id is {{ props.id ? props.id : 'undefined' }}</p>
    <div v-if="props.id">
      <PerformSongsDropdown v-if="performSongsList" :items="performSongsList" />
      <PerformSongsRandomButton v-if="performSongsList" :items="performSongsList" :current-id="Number(props.id)" />
      <PerformSongCard :perform-song="performSong" :image-url="imageUrl" />
    </div>
  </v-container>
</template>

<script lang="ts" setup>
import PerformSongCard from '@/components/PerformSongCard.vue';
import PerformSongsDropdown from '@/components/PerformSongsDropdown.vue';
import PerformSongsRandomButton from '@/components/PerformSongsRandomButton.vue';
import PerformSongEdit from '@/components/PerformSongEdit.vue';
import { computed, nextTick, ref, watch, watchEffect } from 'vue'
import Axios from 'axios';
Axios.defaults.baseURL = '/api';
import { readPerformSong, PerformSongRead, getSpotifyImageUrl, readPerformSongsList } from '@/api';
import { onMounted } from 'vue';
import { useAppStore } from '@/store/app';
const app = useAppStore()
const props = defineProps<{
  id: number | string | undefined;
}>();
const performSong = ref<PerformSongRead>();
const imageUrl = ref('');
const performSongsList = ref<PerformSongRead[]>();
onMounted(async () => {
  await app.loadPerformSongs()
  performSongsList.value = app.performSongs
})
watchEffect(async () => {
  imageUrl.value = '';
  // performSong.value = await readPerformSong(Number(props.id)).then((res) => res.data);
  performSong.value = app.getPerformSongById(Number(props.id))
})
watchEffect(async () => {
  if (performSong.value && performSong.value.spotify_id) {
    imageUrl.value = await getSpotifyImageUrl(performSong.value.spotify_id).then((res) => res.data);
  }
})
</script>

