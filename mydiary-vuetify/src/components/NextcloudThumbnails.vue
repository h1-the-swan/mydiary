<template>
  <div v-if="nextCloudThumbs">
    <v-form @submit.prevent="onSubmit">
      <v-row>
        <v-col
          v-for="(nImage) in nextCloudThumbs"
          :key="nImage.url"
          class="d-flex child-flex nextcloud-thumb"
          :class="{selectedImg: nImage.selected}"
          cols="4"
        >
        <v-img
          :src="nImage.src"
          aspect-ratio="1"
          @click="nImage.selected = !nImage.selected"
        ></v-img>
        </v-col>
      </v-row>
      <v-btn class="mt-2" type="submit" block>Submit</v-btn>
    </v-form>
  </div>
</template>

<script setup lang="ts">
import Axios from 'axios'
Axios.defaults.baseURL = '/api'
import { nextcloudPhotosThumbnailUrls } from '@/api'
import { ref, watch, watchEffect } from 'vue';
const props = defineProps<{
  dt: string;
}>()
interface INextCloudThumb {
  url: string;
  src: string;
  selected: boolean;
}
const nextCloudThumbs = ref<INextCloudThumb[]>([])
async function fetchImageUrls() {
  const imgUrls = (await nextcloudPhotosThumbnailUrls(props.dt)).data
  nextCloudThumbs.value = imgUrls.map((url => {
    return {
      url: url,
      src: `/api/nextcloud/thumbnail_img?url=${url}`,
      selected: false
    }
  }))
}
watch(props, fetchImageUrls, { immediate: true })
watchEffect(() => {
  const numSelected = nextCloudThumbs.value.filter((t => t.selected)).length
  console.log(`${numSelected} selected!`)
  console.log(nextCloudThumbs.value)
})

function onSubmit() {
  const numSelected = nextCloudThumbs.value.filter((t => t.selected)).length
  console.log(`submitted! ${numSelected} selected!`)

}
</script>

<style>
.nextcloud-thumb {
  opacity: 50%;
}

.nextcloud-thumb.selectedImg {
  opacity: 100%;
}
</style>