<template>
    <div>
        <photo-grid
            :items="items"
            badge="uploaded"
            @toggle="(item) => $emit('toggle', item)"
        />
        <p v-if="!items.length" class="text-medium-emphasis mt-2">
            No uploaded images for this day.
        </p>
        <v-file-input
            v-model="pendingFiles"
            class="mt-4"
            label="Upload images"
            accept="image/*"
            multiple
            show-size
            prepend-icon="mdi-camera"
            :disabled="!noteExists"
            :hint="noteExists ? '' : 'Initialize the note before uploading'"
            persistent-hint
        />
        <v-btn
            class="mt-2"
            block
            :loading="uploading"
            :disabled="!noteExists || !pendingFiles.length"
            @click="onUpload"
        >
            Upload
        </v-btn>
        <v-alert
            v-if="uploadError"
            class="mt-2"
            type="error"
            closable
            @click:close="uploadError = ''"
        >
            {{ uploadError }}
        </v-alert>
    </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { uploadImagesToNote } from '@/api'
import { IPhotoItem } from '@/composables/usePhotoSelection'
import PhotoGrid from '@/components/PhotoGrid.vue'

const props = defineProps<{
    dt: string
    joplinNoteId?: string
    items: IPhotoItem[]
}>()
const emit = defineEmits<{
    toggle: [item: IPhotoItem]
    uploaded: []
}>()

const pendingFiles = ref<File[]>([])
const uploading = ref(false)
const uploadError = ref('')

const noteExists = computed<boolean>(() => {
    return !!props.joplinNoteId && props.joplinNoteId !== 'does_not_exist'
})

async function onUpload() {
    if (!props.joplinNoteId || !pendingFiles.value.length) return
    uploading.value = true
    uploadError.value = ''
    try {
        await uploadImagesToNote(
            props.joplinNoteId,
            { files: pendingFiles.value },
            { dt: props.dt }
        )
        pendingFiles.value = []
        emit('uploaded')
    } catch (e: any) {
        uploadError.value =
            e?.response?.data?.detail || e?.message || 'upload failed'
    } finally {
        uploading.value = false
    }
}
</script>
