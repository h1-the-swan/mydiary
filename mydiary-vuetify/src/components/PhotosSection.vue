<template>
    <div class="mt-4">
        <v-tabs v-model="tab" density="compact">
            <v-tab value="iphone">iPhone photos</v-tab>
            <v-tab value="uploads">Uploads</v-tab>
        </v-tabs>
        <v-window v-model="tab" class="mt-2">
            <v-window-item value="iphone">
                <photo-grid
                    :items="iphone.items.value"
                    @toggle="(item) => (item.selected = !item.selected)"
                />
                <p
                    v-if="!iphone.items.value.length"
                    class="text-medium-emphasis mt-2"
                >
                    No synced iPhone photos for this day.
                </p>
            </v-window-item>
            <v-window-item value="uploads">
                <uploads-photo-tab
                    :dt="dt"
                    :joplin-note-id="joplinNoteId"
                    :items="uploads.items.value"
                    @toggle="(item) => (item.selected = !item.selected)"
                    @uploaded="onUploaded"
                />
            </v-window-item>
        </v-window>
        <v-btn
            class="mt-4"
            block
            :loading="syncing"
            :disabled="syncDisabled"
            @click="onSync"
        >
            Sync selection to note
        </v-btn>
        <v-alert
            v-if="syncError"
            class="mt-2"
            type="error"
            closable
            @click:close="syncError = ''"
        >
            {{ syncError }}
        </v-alert>
    </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, watchEffect } from 'vue'
import Axios from 'axios'
Axios.defaults.baseURL = '/api'
import {
    joplinNoteImages,
    MyDiaryImageRead,
    nextcloudPhotosThumbnailUrls,
    syncNoteImages,
    uploadedImagesForDay,
} from '@/api'
import {
    thumbnailSrc,
    usePhotoSelection,
} from '@/composables/usePhotoSelection'
import PhotoGrid from '@/components/PhotoGrid.vue'
import UploadsPhotoTab from '@/components/UploadsPhotoTab.vue'
import { useAppStore } from '@/store/app'

const props = defineProps<{
    dt: string
    joplinNoteId?: string
}>()

const app = useAppStore()
const tab = ref('iphone')
const syncing = ref(false)
const syncError = ref('')
const noteImages = ref<MyDiaryImageRead[]>([])

const iphone = usePhotoSelection()
const uploads = usePhotoSelection()

const noteExists = computed<boolean>(() => {
    return !!props.joplinNoteId && props.joplinNoteId !== 'does_not_exist'
})
const syncDisabled = computed<boolean>(() => {
    return !noteExists.value || !(iphone.dirty.value || uploads.dirty.value)
})

async function fetchIphonePhotos() {
    const paths = (await nextcloudPhotosThumbnailUrls(props.dt)).data
    iphone.items.value = paths.map((path) => ({
        path,
        src: thumbnailSrc(path),
        selected: false,
        existing: false,
        isUpload: false,
    }))
}
async function fetchUploads() {
    const rows = (await uploadedImagesForDay(props.dt)).data
    uploads.items.value = rows
        .filter((row) => !!row.nextcloud_path)
        .map((row) => ({
            path: row.nextcloud_path as string,
            src: thumbnailSrc(row.nextcloud_path as string),
            selected: false,
            existing: false,
            isUpload: true,
        }))
}
async function fetchNoteImages() {
    noteImages.value = []
    if (noteExists.value && props.joplinNoteId) {
        noteImages.value = (await joplinNoteImages(props.joplinNoteId)).data
    }
}
watch(() => props.dt, fetchIphonePhotos, { immediate: true })
watch(() => props.dt, fetchUploads, { immediate: true })
watch(() => props.joplinNoteId, fetchNoteImages, { immediate: true })

// mark grid items already present in the note (full opacity, pre-selected)
watchEffect(() => {
    const existingPaths = noteImages.value
        .map((img) => img.nextcloud_path)
        .filter((path): path is string => !!path)
    iphone.applyExisting(existingPaths)
    uploads.applyExisting(existingPaths)
})

async function onSync() {
    if (!props.joplinNoteId) return
    // full desired set: both tabs' selections, plus any note images that
    // belong to neither tab's universe (defensive: e.g. an upload row from
    // another day), which should be preserved
    const gridPaths = new Set(
        [...iphone.items.value, ...uploads.items.value].map(
            (item) => item.path
        )
    )
    const outOfGridPaths = noteImages.value
        .map((img) => img.nextcloud_path)
        .filter((path): path is string => !!path && !gridPaths.has(path))
    const desired = [
        ...iphone.selectedPaths.value,
        ...uploads.selectedPaths.value,
        ...outOfGridPaths,
    ]
    syncing.value = true
    syncError.value = ''
    try {
        await syncNoteImages(props.joplinNoteId, desired, { dt: props.dt })
        app.calendarShouldUpdate = true
        await fetchNoteImages()
        await fetchUploads()
    } catch (e: any) {
        syncError.value =
            e?.response?.data?.detail || e?.message || 'sync failed'
    } finally {
        syncing.value = false
    }
}
async function onUploaded() {
    await fetchUploads()
    await fetchNoteImages()
    app.calendarShouldUpdate = true
}
</script>
