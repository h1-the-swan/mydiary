import { computed, ref } from 'vue'

export interface IPhotoItem {
    path: string // percent-encoded nextcloud path (canonical identifier)
    src: string
    selected: boolean
    existing: boolean // whether this image is currently in the joplin note
    isUpload: boolean
}

export function thumbnailSrc(path: string): string {
    return `/api/nextcloud/thumbnail_img?url=${path}`
}

export function usePhotoSelection() {
    const items = ref<IPhotoItem[]>([])

    // note: only reads item.path here (never item.selected), so calling this
    // from a watchEffect will not re-trigger when the user toggles selection
    function applyExisting(existingPaths: string[]) {
        items.value.forEach((item) => {
            const val = existingPaths.includes(item.path)
            item.existing = val
            item.selected = val
        })
    }

    const selectedPaths = computed<string[]>(() =>
        items.value.filter((item) => item.selected).map((item) => item.path)
    )
    const dirty = computed<boolean>(() =>
        items.value.some((item) => item.selected !== item.existing)
    )

    return { items, applyExisting, selectedPaths, dirty }
}
