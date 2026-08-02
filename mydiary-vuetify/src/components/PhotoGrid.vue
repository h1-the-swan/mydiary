<template>
    <v-row dense>
        <v-col
            v-for="item in items"
            :key="item.path"
            class="d-flex child-flex"
            cols="4"
            sm="3"
            md="2"
        >
            <!-- v-img lazy-loads via IntersectionObserver unless `eager` is set -->
            <v-img
                :src="item.src"
                class="photo-thumb rounded-lg"
                :class="{ selectedImg: item.selected }"
                aspect-ratio="1"
                cover
                role="button"
                tabindex="0"
                :aria-pressed="item.selected"
                @click="$emit('toggle', item)"
                @keydown.enter.prevent="$emit('toggle', item)"
                @keydown.space.prevent="$emit('toggle', item)"
            >
                <template #placeholder>
                    <div class="d-flex align-center justify-center fill-height">
                        <v-progress-circular indeterminate color="primary" />
                    </div>
                </template>
                <template #error>
                    <div
                        class="d-flex align-center justify-center fill-height thumb-error"
                    >
                        <v-icon icon="mdi-image-broken-variant" />
                    </div>
                </template>
                <v-chip
                    v-if="badge"
                    class="thumb-badge"
                    size="x-small"
                    variant="elevated"
                >
                    {{ badge }}
                </v-chip>
                <v-icon
                    v-if="item.selected"
                    class="thumb-check"
                    icon="mdi-check-circle"
                    color="primary"
                />
            </v-img>
        </v-col>
    </v-row>
</template>

<script setup lang="ts">
import { IPhotoItem } from '@/composables/usePhotoSelection'
defineProps<{
    items: IPhotoItem[]
    badge?: string
}>()
defineEmits<{
    toggle: [item: IPhotoItem]
}>()
</script>

<style scoped>
/* Unselected photos are dimmed, but only slightly — the positive signal for
   selection is the ring and the check, not the absence of transparency. */
.photo-thumb {
    cursor: pointer;
    opacity: 0.7;
    outline: 2px solid transparent;
    outline-offset: -2px;
    transition:
        opacity 150ms ease,
        outline-color 150ms ease;
}

.photo-thumb:hover,
.photo-thumb:focus-visible {
    opacity: 1;
}

.photo-thumb.selectedImg {
    opacity: 1;
    outline-color: rgb(var(--v-theme-primary));
}

.thumb-badge {
    position: absolute;
    top: 4px;
    left: 4px;
}

.thumb-check {
    position: absolute;
    top: 4px;
    right: 4px;
    border-radius: 50%;
    background: rgb(var(--v-theme-surface));
}

.thumb-error {
    background: rgba(var(--v-theme-on-surface), 0.06);
}

@media (prefers-reduced-motion: reduce) {
    .photo-thumb {
        transition: none;
    }
}
</style>
