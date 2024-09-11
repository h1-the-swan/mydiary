<template>
    <div v-if="nextCloudThumbs">
        <v-form @submit.prevent="onSubmit">
            <v-row>
                <v-col
                    v-for="nImage in nextCloudThumbs"
                    :key="nImage.url"
                    class="d-flex child-flex nextcloud-thumb"
                    :class="{ selectedImg: nImage.selected }"
                    cols="4"
                >
                    <v-img
                        :src="nImage.src"
                        aspect-ratio="1"
                        @click="nImage.selected = !nImage.selected"
                    ></v-img>
                </v-col>
            </v-row>
            <v-btn :loading="loading" class="mt-2" type="submit" block>Submit</v-btn>
        </v-form>
    </div>
</template>

<script setup lang="ts">
import Axios from 'axios'
Axios.defaults.baseURL = '/api'
import {
    nextcloudPhotosThumbnailUrls,
    joplinNoteImages,
    MyDiaryImageRead,
    nextcloudPhotosAddToJoplin,
} from '@/api'
import { ref, watch, watchEffect } from 'vue'
const props = defineProps<{
    dt: string
    joplinNoteId?: string
}>()
interface INextCloudThumb {
    url: string
    src: string
    selected: boolean
}
const nextCloudThumbs = ref<INextCloudThumb[]>([])
const diaryNoteImages = ref<MyDiaryImageRead[]>([])
const loading = ref(false)
async function fetchImageUrls() {
    const imgUrls = (await nextcloudPhotosThumbnailUrls(props.dt)).data
    nextCloudThumbs.value = imgUrls.map((url) => {
        return {
            url: url,
            src: `/api/nextcloud/thumbnail_img?url=${url}`,
            selected: false,
        }
    })
}
async function fetchJoplinNoteImages() {
    diaryNoteImages.value = []
    if (props.joplinNoteId) {
        diaryNoteImages.value = (
            await joplinNoteImages(props.joplinNoteId)
        ).data
    }
}
watch(props, fetchImageUrls, { immediate: true })
watch(props, fetchJoplinNoteImages, { immediate: true })
watchEffect(() => {
    const existingUrls = diaryNoteImages.value.map(
        (item) => item.nextcloud_path
    )
    nextCloudThumbs.value.forEach(
        (item) => (item.selected = existingUrls.includes(item.url))
    )
})
watchEffect(() => {
    const numSelected = nextCloudThumbs.value.filter((t) => t.selected).length
    console.log(`${numSelected} selected!`)
    console.log(nextCloudThumbs.value)
})

async function onSubmit() {
    const selected = nextCloudThumbs.value.filter((t) => t.selected)
    loading.value = true
    const response = (await nextcloudPhotosAddToJoplin(props.joplinNoteId, selected.map((t) => t.url))).data
    console.log(response.value)
    loading.value = false
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
