<template>
  <v-card v-if="performSong" style="max-width: 50em;">
    <v-img v-if="imageUrl" :src="imageUrl" cover></v-img>
    <v-card-title>
      {{ performSong.name }}
    </v-card-title>
    <v-card-subtitle>{{ performSong.artist_name }}</v-card-subtitle>
    <v-card-text>
      <p>{{ performSong.learned ? "Learned" : "Not Learned" }}</p>
      <p v-if="performSong.key">Key: {{ performSong.key }}</p>
      <p v-if="performSong.capo">Capo: {{ performSong.capo }}</p>
      <p v-if="performSong.notes">Notes: {{ performSong.notes }}</p>
      <p v-if="performSong.lyrics">Lyrics: {{ performSong.lyrics }}</p>
      <p v-if="performSong.learned_dt">Learned: {{ new Date(performSong.learned_dt).toDateString() }}</p>
    </v-card-text>
  </v-card>
</template>

<script lang="ts" setup>
import { PerformSongRead } from '@/api';
import { watchEffect } from 'vue';
const props = defineProps<{
  performSong?: PerformSongRead;
  imageUrl?: string;
}>();
</script>