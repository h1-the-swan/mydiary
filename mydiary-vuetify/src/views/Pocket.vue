<template>
  <v-container>
    <p v-if="numPocketArticles">
      {{ numPocketArticles }} Pocket articles in database.
    </p>
    <v-btn @click="onClick">
      pocketArticles
    </v-btn>
    <v-data-table v-if="pocketArticles" :headers="headers" :items="pocketArticles"></v-data-table>
    <v-progress-circular indeterminate color="primary" v-else></v-progress-circular>

  </v-container>
</template>

<script lang="ts" setup>
import { PocketArticleRead, readPocketArticles, countPocketArticles } from '@/api';
import { onMounted } from 'vue';
import { ref } from 'vue';
import Axios from 'axios';
Axios.defaults.baseURL = '/api';
const numPocketArticles = ref<Number>()
const pocketArticles = ref<PocketArticleRead[]>();
const headers = [
  { title: "Title", key: "given_title" },
  {
    title: "Added",
    key: "time_added",
  }
];
onMounted(async () => {
  numPocketArticles.value = await countPocketArticles().then((res) => res.data);
  pocketArticles.value = await readPocketArticles({ limit: 1000 }).then((res) => res.data);
})
function onClick() {
  console.log(pocketArticles.value);
}
</script>