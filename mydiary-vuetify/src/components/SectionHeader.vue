<template>
    <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-3">
        <div class="d-flex align-baseline ga-2 text-overline">
            <span>{{ label }}</span>
            <span v-if="meta" class="text-medium-emphasis text-none text-body-2">
                {{ meta }}
            </span>
        </div>
        <div v-if="$slots.actions" class="d-flex align-center ga-2">
            <slot name="actions" />
        </div>
    </div>
    <v-divider class="mb-4" />
</template>

<script setup lang="ts">
defineProps<{
    /** Uppercase section name, e.g. "Photos". */
    label: string
    /** Live detail shown beside the label, e.g. a count or a distance. */
    meta?: string
}>()
</script>
