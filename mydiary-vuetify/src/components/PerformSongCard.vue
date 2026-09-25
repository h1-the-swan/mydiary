<template>
  <v-card v-if="performSong" border>
    <div class="d-flex flex-column flex-sm-row ga-6 pa-4">
      <v-img
        v-if="imageUrl"
        :src="imageUrl"
        class="album-art rounded-lg flex-grow-0 flex-shrink-0"
        cover
      ></v-img>
      <div class="flex-grow-1 align-self-center">
        <h2 class="text-h4 font-weight-medium">{{ performSong.name }}</h2>
        <p class="text-h6 font-weight-regular text-medium-emphasis mb-4">
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
        <tag-chips
          class="mb-3"
          target-type="song"
          :target-id="String(performSong.id)"
        />

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
      <div v-router-links class="prose" v-html="md.render(performSong.lyrics)"></div>
    </v-card-text>
  </v-card>
</template>

<script lang="ts" setup>
import { PerformSongRead } from '@/api';
import { md } from '@/markdown';
import TagChips from '@/components/TagChips.vue';
const props = defineProps<{
  performSong?: PerformSongRead;
  imageUrl?: string;
}>();
</script>

<style scoped>
/* The art is the most recognisable thing about a song, so it leads the card.
   Square, and sized to stay prominent without pushing the metadata off-screen. */
.album-art {
  width: 100%;
  aspect-ratio: 1;
}

@media (min-width: 600px) {
  .album-art {
    width: 42%;
    min-width: 260px;
    max-width: 440px;
  }
}
</style>
