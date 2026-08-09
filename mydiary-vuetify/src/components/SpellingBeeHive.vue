<template>
    <div class="hive" :style="{ '--hex-w': `${size}px` }">
        <button
            v-for="(hex, i) in hexes"
            :key="`${hex.letter}-${i}`"
            type="button"
            class="hex"
            :class="{ 'hex--center': hex.center }"
            :style="hex.style"
            @click="emit('letter', hex.letter)"
        >
            {{ hex.letter }}
        </button>
    </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
    defineProps<{
        centerLetter: string
        outerLetters: string[]
        /** Width of one hexagon, in px. The board scales from this alone. */
        size?: number
    }>(),
    { size: 92 }
)

const emit = defineEmits<{ letter: [string] }>()

// gap between neighbouring hexes
const GAP = 8
// height of a pointy-top hexagon relative to its width
const RATIO = 1.1547

/**
 * Six hexes ring the centre one. For a pointy-top hexagon of width w and
 * height h, neighbours sit at (±(w+gap), 0) horizontally and at
 * (±(w+gap)/2, ±(0.75h + gap)) on the diagonals — the 0.75 because adjacent
 * rows interlock rather than stacking.
 */
const hexes = computed(() => {
    const w = props.size
    const h = w * RATIO
    const dx = (w + GAP) / 2
    const dy = 0.75 * h + GAP
    const offsets = [
        [-dx, -dy],
        [dx, -dy],
        [-(w + GAP), 0],
        [w + GAP, 0],
        [-dx, dy],
        [dx, dy],
    ]

    const place = (x: number, y: number) => ({
        left: `calc(50% + ${x}px)`,
        top: `calc(50% + ${y}px)`,
    })

    return [
        { letter: props.centerLetter, center: true, style: place(0, 0) },
        ...props.outerLetters.map((letter, i) => ({
            letter,
            center: false,
            style: place(offsets[i][0], offsets[i][1]),
        })),
    ]
})
</script>

<style scoped>
.hive {
    position: relative;
    /* three hexes wide, three rows deep, plus the gaps */
    width: calc(var(--hex-w) * 3 + 16px);
    height: calc(var(--hex-w) * 3 + 16px);
    margin: 0 auto;
}

.hex {
    position: absolute;
    width: var(--hex-w);
    height: calc(var(--hex-w) * 1.1547);
    /* the clip-path keeps the flat vertical sides, so a default button border
       would survive as a dark bar down each edge */
    border: 0;
    padding: 0;
    appearance: none;
    transform: translate(-50%, -50%);
    clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
    background: rgba(var(--v-theme-on-surface), 0.08);
    color: rgb(var(--v-theme-on-surface));
    font-size: calc(var(--hex-w) * 0.34);
    font-weight: 700;
    letter-spacing: 0.04em;
    cursor: pointer;
    transition: background-color 120ms ease, transform 80ms ease;
}

.hex:hover {
    background: rgba(var(--v-theme-on-surface), 0.16);
}

.hex:active {
    transform: translate(-50%, -50%) scale(0.94);
}

/* the mandatory letter, so it reads as the one you can't leave out */
.hex--center {
    background: rgb(var(--v-theme-primary));
    color: rgb(var(--v-theme-on-primary, 255, 255, 255));
}

.hex--center:hover {
    background: rgb(var(--v-theme-primary));
    filter: brightness(1.1);
}
</style>
