<template>
  <v-card v-if="performSong" border>
    <div class="d-flex flex-column flex-sm-row ga-4 pa-4">
      <v-img
        v-if="imageUrl"
        :src="imageUrl"
        class="album-art rounded-lg flex-grow-0"
        cover
      ></v-img>
      <div class="flex-grow-1">
        <h2 class="text-h5 font-weight-medium">{{ performSong.name }}</h2>
        <p class="text-subtitle-1 text-medium-emphasis mb-3">
          {{ performSong.artist_name }}
        </p>

        <div class="d-flex flex-wrap ga-2 mb-3">
          <v-chip
            size="small"
            :color="performSong.learned ? 'success' : undefined"
            :prepend-icon="performSong.learned ? 'mdi-check' : undefined"
          >
            {{ performSong.learned ? "Learned" : "Not learned" }}
          </v-chip>
          <v-chip v-if="performSong.key" size="small" variant="outlined">
            Key {{ performSong.key }}
          </v-chip>
          <v-chip v-if="performSong.capo" size="small" variant="outlined">
            Capo {{ performSong.capo }}
          </v-chip>
        </div>

        <p v-if="performSong.notes" class="text-body-2 mb-2">
          {{ performSong.notes }}
        </p>
        <p
          v-if="performSong.learned_dt"
          class="text-body-2 text-medium-emphasis mb-0"
        >
          Learned {{ new Date(performSong.learned_dt).toLocaleDateString() }}
        </p>
      </div>
    </div>

    <v-divider v-if="performSong.lyrics" />
    <v-card-text v-if="performSong.lyrics">
      <div class="text-overline text-medium-emphasis mb-2">Lyrics</div>
      <div class="prose" v-html="md.render(performSong.lyrics)"></div>
    </v-card-text>
  </v-card>
</template>

<script lang="ts" setup>
import { PerformSongRead } from '@/api';
import markdownit from 'markdown-it';
const md = markdownit()
const props = defineProps<{
  performSong?: PerformSongRead;
  imageUrl?: string;
}>();
</script>

<style scoped>
.album-art {
  width: 100%;
  max-width: 220px;
  aspect-ratio: 1;
}
</style>
