<template>
  <v-container>
    <p v-if="numPocketArticles">
      {{ numPocketArticles }} Pocket articles in database.
    </p>
    <v-btn @click="onClick">
      pocketArticles
    </v-btn>
    <v-data-table v-if="pocketArticles" :headers="headers" :items="pocketArticles">
      <template #[`item.tags`]="{ item }">
        <div class="d-flex flex-wrap ga-1 py-1">
          <v-chip
            v-for="tag in item.tags"
            :key="tag.id"
            size="x-small"
            variant="outlined"
            :to="tagRoute(tag.key)"
          >
            #{{ tag.key }}
          </v-chip>
        </div>
      </template>
    </v-data-table>
    <v-progress-circular indeterminate color="primary" v-else></v-progress-circular>

  </v-container>
</template>

<script lang="ts" setup>
import { PocketArticleRead, readPocketArticles, countPocketArticles } from '@/api';
import { onMounted } from 'vue';
import { ref } from 'vue';
import Axios from 'axios';
import { tagRoute } from '@/tags';
Axios.defaults.baseURL = '/api';
const numPocketArticles = ref<number>()
const pocketArticles = ref<PocketArticleRead[]>();
const headers = [
  { title: "Title", key: "given_title" },
  {
    title: "Added",
    key: "time_added",
  },
  { title: "Tags", key: "tags", sortable: false },
];
onMounted(async () => {
  numPocketArticles.value = await countPocketArticles().then((res) => res.data);
  pocketArticles.value = await readPocketArticles({ limit: 1000 }).then((res) => res.data);
})
function onClick() {
  console.log(pocketArticles.value);
}
</script>