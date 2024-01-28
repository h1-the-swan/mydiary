<template>
  <div v-if="imgUrls">
    <p v-for="(url) in imgUrls" :key="url">
      {{ url }}
    </p>
  </div>
</template>

<script setup lang="ts">
import Axios from 'axios'
Axios.defaults.baseURL = '/api'
import { nextcloudPhotosThumbnailUrls } from '@/api'
import { ref, watch } from 'vue';
const props = defineProps<{
  dt: string;
}>()
const imgUrls = ref<string[]>()
async function fetchImageUrls() {
  imgUrls.value = undefined
  imgUrls.value = (await nextcloudPhotosThumbnailUrls(props.dt)).data
}
watch(props, fetchImageUrls, {immediate: true})
</script>