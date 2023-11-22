<template>
  <v-btn @click="onClick" :loading="loading">
    Save recent Spotify tracks
  </v-btn>
  <v-snackbar v-model="snackbar" timeout="3000">
    {{ text }}

    <template v-slot:actions>
      <v-btn color="green" variant="text" @click="snackbar = false">
        Close
      </v-btn>
    </template>
  </v-snackbar>
</template>

<script lang="ts" setup>
import Axios from 'axios';
Axios.defaults.baseURL = '/api';
import { spotifySaveRecentTracksToDatabase } from '@/api';
import { computed } from 'vue';
import { ref } from 'vue';

const loading = ref(false);
const snackbar = ref(false);
const numSaved = ref(0);
const text = computed(() => {
  return `${numSaved.value} tracks saved to database`;
})

async function onClick() {
  loading.value = true;
  await spotifySaveRecentTracksToDatabase()
    .then((res) => res.data)
    .then((res) => {
      numSaved.value = res;
      snackbar.value = true;
      loading.value = false;

    });
}
</script>