<template>
    <section v-if="cards.length" class="mb-10">
        <section-header label="Learning" :meta="`${cards.length}`" />
        <div class="d-flex flex-column ga-3">
            <v-card v-for="card in cards" :key="card.row.song.id" border class="pa-4">
                <div class="d-flex flex-wrap align-center ga-3">
                    <div class="flex-grow-1">
                        <router-link
                            :to="{ name: 'performSong', params: { id: card.row.song.id } }"
                            class="text-subtitle-1 font-weight-medium"
                        >
                            {{ card.row.song.name }}
                        </router-link>
                        <div class="text-body-2 text-medium-emphasis">
                            {{ card.row.song.artist_name }}
                            <span v-if="card.row.instruments.length">
                                · {{ card.row.instruments.map((i) => INSTRUMENT_LABELS[i]).join(', ') }}
                            </span>
                        </div>
                    </div>
                    <div class="text-body-2 text-medium-emphasis">
                        {{ card.row.last_practiced_at ? `Practiced ${shortDate(card.row.last_practiced_at)}` : 'Not practiced yet' }}
                    </div>
                    <v-btn
                        v-if="card.row.instruments.length"
                        color="primary"
                        variant="flat"
                        prepend-icon="mdi-play"
                        :to="{ name: 'songPractice', params: { id: card.row.song.id } }"
                    >
                        Practice
                    </v-btn>
                    <v-btn
                        v-else
                        prepend-icon="mdi-plus"
                        :to="{ name: 'performSong', params: { id: card.row.song.id }, hash: '#arrangements' }"
                    >
                        Add a sheet
                    </v-btn>
                </div>
                <div v-if="card.bars.length" class="d-flex ga-1 mt-3">
                    <div
                        v-for="bar in card.bars"
                        :key="bar.key"
                        class="level-bar"
                        :class="`bg-${levelColor(bar.level)}`"
                        :title="`${bar.key}: ${LEVEL_LABELS[bar.level]}`"
                    ></div>
                </div>
                <div v-if="card.allMemorized" class="text-body-2 mt-2">
                    Every section is memorized. Mark it learned when you're ready.
                </div>
            </v-card>
        </div>
    </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import SectionHeader from '@/components/SectionHeader.vue'
import { parseSheet, sectionKeys } from '@/chordpro'
import { INSTRUMENT_LABELS, LEVEL_LABELS, levelColor, levelMap, shortDate } from '@/practice'
import { LearningSongRead, listLearningSongs } from '@/api'

const rows = ref<LearningSongRead[]>([])

// the backend already sorts: never practiced first, then the longest idle
const cards = computed(() =>
    rows.value.map((row) => {
        const levels = levelMap(row.levels)
        const bars = (row.sheet ? sectionKeys(parseSheet(row.sheet)) : []).map((key) => ({
            key,
            level: levels[key] ?? 'full',
        }))
        return { row, bars, allMemorized: bars.length > 0 && bars.every((b) => b.level === 'memorized') }
    })
)

onMounted(async () => {
    rows.value = (await listLearningSongs()).data
})
</script>

<style scoped>
.level-bar {
    flex: 1;
    height: 6px;
    border-radius: 3px;
}
</style>
