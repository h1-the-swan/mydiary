<template>
    <v-row>
        <v-col
            v-for="item in items"
            :key="item.path"
            class="d-flex child-flex photo-thumb"
            :class="{ selectedImg: item.selected }"
            cols="4"
        >
            <!-- v-img lazy-loads via IntersectionObserver unless `eager` is set -->
            <v-img
                :src="item.src"
                aspect-ratio="1"
                cover
                @click="$emit('toggle', item)"
            >
                <template #placeholder>
                    <div class="d-flex align-center justify-center fill-height">
                        <v-progress-circular
                            indeterminate
                            color="grey-lighten-1"
                        />
                    </div>
                </template>
                <template #error>
                    <div
                        class="d-flex align-center justify-center fill-height bg-grey-lighten-3"
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
.photo-thumb {
    opacity: 50%;
    cursor: pointer;
}

.photo-thumb.selectedImg {
    opacity: 100%;
}

.thumb-badge {
    position: absolute;
    top: 4px;
    left: 4px;
}
</style>
