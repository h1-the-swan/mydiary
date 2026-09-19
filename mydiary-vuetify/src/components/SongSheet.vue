<template>
    <div class="song-sheet" :style="{ fontSize: `${scale}rem` }">
        <section
            v-for="(occ, i) in parsed.occurrences"
            :id="`sheet-sec-${i}`"
            :key="i"
            class="sheet-section"
        >
            <div class="sheet-label text-overline">
                <span class="level-dot" :class="`bg-${levelColor(levelOf(occ.key))}`"></span>
                {{ occ.key }}
            </div>
            <div
                class="sheet-lines"
                :class="{ faded: shownLevel(occ.key) !== 'full' }"
                @click="onSectionClick($event, occ.key)"
            >
                <template v-for="(line, j) in occ.lines" :key="j">
                    <div
                        v-if="showLine(line)"
                        class="sheet-line"
                        :class="{ comment: line.comment, blank: isBlankLine(line) }"
                    >
                        <span
                            v-for="(seg, k) in lineSegments(line, shownLevel(occ.key))"
                            :key="k"
                            class="seg"
                        >
                            <span
                                v-if="withChords(line)"
                                class="chord"
                                @click.stop="seg.chord && emit('chord', seg.chord)"
                                >{{ seg.chord ?? ' ' }}</span
                            >
                            <span class="seg-text"
                                ><span
                                    v-for="(run, r) in seg.runs"
                                    :key="r"
                                    :class="{ 'hidden-text': run.hidden }"
                                    >{{ run.text }}</span
                                ></span
                            >
                        </span>
                    </div>
                </template>
            </div>
        </section>
    </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { lineSegments, type Level, type ParsedSheet, type SheetLine } from '@/chordpro'
import { levelColor } from '@/practice'

const props = withDefaults(
    defineProps<{
        parsed: ParsedSheet
        levels?: Record<string, Level>
        /** Ignore levels and show every word. */
        showAll?: boolean
        /** Hide chords, for practice away from the instrument. */
        lyricsOnly?: boolean
        /** Font size in rem. */
        scale?: number
    }>(),
    { levels: () => ({}), showAll: false, lyricsOnly: false, scale: 1 }
)
const emit = defineEmits<{ chord: [name: string] }>()

// how long a tapped faded section stays fully shown
const PEEK_MS = 4000
const peeked = ref(new Set<string>())
const timers: number[] = []

function levelOf(key: string): Level {
    return props.levels[key] ?? 'full'
}

function shownLevel(key: string): Level {
    return props.showAll || peeked.value.has(key) ? 'full' : levelOf(key)
}

function isBlankLine(line: SheetLine): boolean {
    return !line.text.trim() && !line.chords.length && !line.comment
}

function withChords(line: SheetLine): boolean {
    return !props.lyricsOnly && line.chords.length > 0
}

function showLine(line: SheetLine): boolean {
    // a chords-only line has nothing to show without its chords
    return !(props.lyricsOnly && line.chords.length && !line.text.trim())
}

function onSectionClick(event: MouseEvent, key: string) {
    if (shownLevel(key) === 'full') return
    // a peek, not a page turn: keep the tap from reaching the scroll handler
    event.stopPropagation()
    peeked.value = new Set([...peeked.value, key])
    timers.push(
        window.setTimeout(() => {
            const next = new Set(peeked.value)
            next.delete(key)
            peeked.value = next
        }, PEEK_MS)
    )
}

onBeforeUnmount(() => timers.forEach((t) => window.clearTimeout(t)))
</script>

<style scoped>
.song-sheet {
    line-height: 1.35;
}
.sheet-section {
    margin-bottom: 1.25em;
    break-inside: avoid;
}
.sheet-label {
    display: flex;
    align-items: center;
    gap: 0.5em;
    line-height: 1.8;
}
.level-dot {
    display: inline-block;
    width: 0.6em;
    height: 0.6em;
    border-radius: 50%;
}
.sheet-lines.faded {
    cursor: pointer;
}
.sheet-line {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
}
.sheet-line.blank {
    height: 0.75em;
}
.sheet-line.comment {
    font-style: italic;
    color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
/* a chord stacked over the text it starts; the pair is as wide as the wider */
.seg {
    display: inline-flex;
    flex-direction: column;
    max-width: 100%;
    min-width: 0;
}
.chord {
    padding-right: 0.35em;
    font-size: 0.9em;
    font-weight: 700;
    color: rgb(var(--v-theme-primary));
    white-space: pre;
    cursor: pointer;
}
/* not Markdown: these are plain text runs whose spaces carry the chord offsets */
.seg-text {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}
.hidden-text {
    color: transparent;
    text-decoration: underline dotted;
    text-decoration-color: rgba(var(--v-theme-on-surface), 0.35);
}
</style>
