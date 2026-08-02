<template>
    <v-container class="mydiary-page py-6">
        <header v-if="title || $slots.eyebrow || $slots.actions" class="mb-6">
            <div class="d-flex align-end justify-space-between flex-wrap ga-4">
                <div>
                    <div
                        v-if="eyebrow || $slots.eyebrow"
                        class="text-overline text-medium-emphasis"
                    >
                        <slot name="eyebrow">{{ eyebrow }}</slot>
                    </div>
                    <h1 class="text-h4 font-weight-medium">
                        <slot name="title">{{ title }}</slot>
                    </h1>
                </div>
                <div v-if="$slots.actions" class="d-flex align-center ga-2">
                    <slot name="actions" />
                </div>
            </div>
        </header>
        <slot />
    </v-container>
</template>

<script setup lang="ts">
defineProps<{
    /** Small uppercase label above the title, e.g. the weekday. */
    eyebrow?: string
    title?: string
}>()
</script>
