<template>
    <page-shell eyebrow="Spelling Bee" title="Practice">
        <template #actions>
            <v-btn :to="{ name: 'spellingBee' }" prepend-icon="mdi-arrow-left">
                Missed words
            </v-btn>
        </template>

        <div class="reading">
            <v-btn-toggle v-model="mode" mandatory divided class="mb-6">
                <v-btn value="hive" prepend-icon="mdi-hexagon-multiple">Hive</v-btn>
                <v-btn value="drill" prepend-icon="mdi-lightbulb-outline">
                    Recall drill
                </v-btn>
            </v-btn-toggle>

            <v-progress-linear v-if="loading" indeterminate></v-progress-linear>

            <template v-else-if="mode === 'hive'">
                <spelling-bee-hive-game
                    v-if="hives.length"
                    :hives="hives"
                />
                <v-card v-else border>
                    <v-card-text class="text-medium-emphasis">
                        No puzzle has enough recorded words to rebuild a hive yet.
                        Add a few more on the
                        <router-link :to="{ name: 'spellingBee' }">
                            missed words
                        </router-link>
                        page, then come back.
                    </v-card-text>
                </v-card>
            </template>

            <spelling-bee-hint-drill v-else :words="words" :hives="hives" />
        </div>
    </page-shell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import PageShell from '@/components/PageShell.vue'
import SpellingBeeHiveGame from '@/components/SpellingBeeHiveGame.vue'
import SpellingBeeHintDrill from '@/components/SpellingBeeHintDrill.vue'
import { useAppStore } from '@/store/app'

const STORAGE_KEY = 'spellingBeePracticeMode'

const app = useAppStore()
const mode = ref(localStorage.getItem(STORAGE_KEY) ?? 'hive')
const loading = ref(true)

watch(mode, (value) => localStorage.setItem(STORAGE_KEY, value))

const words = computed(() => app.spellingBeeWords ?? [])
const hives = computed(() => app.spellingBeeHives ?? [])

onMounted(async () => {
    await Promise.all([app.loadSpellingBeeWords(), app.loadSpellingBeeHives()])
    loading.value = false
})
</script>
