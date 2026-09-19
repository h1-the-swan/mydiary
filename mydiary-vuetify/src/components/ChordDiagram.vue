<template>
    <div class="chord-diagram" :style="{ width: `${size}px` }">
        <div class="text-body-2 font-weight-medium text-center">{{ chord }}</div>
        <div ref="target" class="chord-diagram-svg"></div>
        <div v-if="missing" class="text-caption text-medium-emphasis text-center">
            no fingering
        </div>
    </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { FretLabelPosition, SVGuitarChord } from 'svguitar'
import type { ChordDefine } from '@/chordpro'
import { STRINGS, fingeringFromDefine, loadChordDb, lookupChord, toSvguitar, type Instrument } from '@/chords'

const props = withDefaults(
    defineProps<{
        chord: string
        instrument: Instrument
        /** The sheet's own fingering, which beats the library. */
        define?: ChordDefine
        /** Which library position to show when there is no define. */
        position?: number
        size?: number
    }>(),
    { define: undefined, position: 0, size: 96 }
)

const target = ref<HTMLDivElement>()
const missing = ref(false)

async function draw() {
    if (!target.value) return
    target.value.innerHTML = ''
    const strings = STRINGS[props.instrument]
    const fingering = props.define
        ? fingeringFromDefine(props.define)
        : lookupChord(await loadChordDb(props.instrument), props.chord)[props.position]
    missing.value = !fingering
    if (!fingering) return
    new SVGuitarChord(target.value)
        .configure({ strings, frets: 4, fretLabelPosition: FretLabelPosition.LEFT, fontFamily: 'inherit' })
        .chord(toSvguitar(fingering, strings))
        .draw()
}

onMounted(draw)
watch(() => [props.chord, props.instrument, props.define, props.position], draw, { deep: true })
</script>

<style scoped>
.chord-diagram-svg :deep(svg) {
    width: 100%;
    height: auto;
}
</style>
