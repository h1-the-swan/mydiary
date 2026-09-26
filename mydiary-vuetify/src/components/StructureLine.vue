<template>
    <div class="d-flex flex-wrap ga-1">
        <v-chip
            v-for="item in items"
            :key="item.index"
            :color="levelColor(levelOf(item.key))"
            :title="`${item.key}: ${LEVEL_LABELS[levelOf(item.key)]}`"
            variant="flat"
            label
            @click="emit('jump', item.index)"
        >
            {{ item.count > 1 ? `${item.abbr}×${item.count}` : item.abbr }}
        </v-chip>
    </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { structure, type Level, type ParsedSheet } from '@/chordpro'
import { LEVEL_LABELS, levelColor } from '@/practice'

const props = withDefaults(
    defineProps<{ parsed: ParsedSheet; levels?: Record<string, Level> }>(),
    { levels: () => ({}) }
)
const emit = defineEmits<{ jump: [index: number] }>()

const items = computed(() => structure(props.parsed))

function levelOf(key: string): Level {
    return props.levels[key] ?? 'full'
}
</script>
