<template>
    <div v-if="nextCloudThumbs && nextCloudThumbs.length">
        <p>Selected synced with note: {{ selectedSyncedWithNote }}</p>
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
                    />
                </v-col>
            </v-row>
            <v-btn
                :loading="loading"
                class="mt-2"
                type="submit"
                block
                :disabled="disabled"
            >
                Submit
            </v-btn>
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
import { computed, ref, watch, watchEffect } from 'vue'
const props = defineProps<{
    dt: string
    joplinNoteId?: string
}>()
interface INextCloudThumb {
    url: string
    src: string
    selected: boolean
    existing: boolean // whether this image is already in the joplin note
}
const nextCloudThumbs = ref<INextCloudThumb[]>([])
const diaryNoteImages = ref<MyDiaryImageRead[]>([])
const loading = ref(false)
const selectedSyncedWithNote = computed<boolean>(() => {
    return nextCloudThumbs.value.every(
        (item) => item.existing === item.selected
    )
})
const disabled = computed<boolean>(() => {
    // submit button will be disabled if any of the conditions is true
    return (
        !props.joplinNoteId ||
        props.joplinNoteId === 'does_not_exist' || // no note; so can't add photos
        selectedSyncedWithNote.value // no change to submit
    )
})
async function fetchImageUrls() {
    const imgUrls = (await nextcloudPhotosThumbnailUrls(props.dt)).data
    nextCloudThumbs.value = imgUrls.map((url) => {
        return {
            url: url,
            src: `/api/nextcloud/thumbnail_img?url=${url}`,
            selected: false,
            existing: false,
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
    nextCloudThumbs.value.forEach((item) => {
        const val = existingUrls.includes(item.url)
        item.existing = val
        item.selected = val
    })
    console.log(diaryNoteImages)
})
watchEffect(() => {
    const numSelected = nextCloudThumbs.value.filter((t) => t.selected).length
    console.log(`${numSelected} selected!`)
    console.log(nextCloudThumbs.value)
})

async function onSubmit() {
    if (!props.joplinNoteId) return
    const selected = nextCloudThumbs.value.filter((t) => t.selected)
    loading.value = true
    const response = (
        await nextcloudPhotosAddToJoplin(
            props.joplinNoteId,
            selected.map((t) => t.url)
        )
    ).data
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
