<template>
    <div>
        <div class="d-flex flex-wrap align-center ga-4 mb-4">
            <v-text-field
                v-model="search"
                class="flex-grow-1 search-field"
                label="Search words"
                prepend-inner-icon="mdi-magnify"
                hide-details
                single-line
                clearable
            ></v-text-field>
            <v-btn-toggle v-model="minMisses" mandatory density="comfortable" divided>
                <v-btn :value="1">All</v-btn>
                <v-btn :value="2">Missed 2+</v-btn>
                <v-btn :value="3">Missed 3+</v-btn>
            </v-btn-toggle>
        </div>

        <v-data-table
            :items="filtered"
            :headers="displayCols"
            :items-per-page="25"
            :search="search"
            :sort-by="[{ key: 'times_missed', order: 'desc' }]"
        >
            <template #item="{ item }">
                <tr>
                    <td>
                        <span class="font-weight-medium">{{ item.word }}</span>
                        <v-chip
                            v-if="item.is_pangram"
                            class="ml-2"
                            size="x-small"
                            color="secondary"
                            prepend-icon="mdi-star-four-points"
                        >
                            Pangram
                        </v-chip>
                    </td>
                    <td>
                        <v-chip size="small" :color="missColor(item.times_missed)">
                            {{ item.times_missed }}
                        </v-chip>
                    </td>
                    <td>{{ formatDate(item.first_missed) }}</td>
                    <td>{{ formatDate(item.last_missed) }}</td>
                    <td>
                        <div v-if="item.definition" class="text-body-2 py-2">
                            <span
                                v-if="item.part_of_speech"
                                class="text-medium-emphasis font-italic"
                            >
                                {{ item.part_of_speech }} —
                            </span>
                            {{ item.definition }}
                        </div>
                        <span
                            v-else-if="notFound.has(item.word)"
                            class="text-disabled text-body-2"
                        >
                            No definition found
                        </span>
                        <v-btn
                            v-else
                            size="small"
                            variant="text"
                            prepend-icon="mdi-book-open-variant"
                            :loading="pending.has(item.word)"
                            @click="lookUp(item)"
                        >
                            Look up
                        </v-btn>
                    </td>
                </tr>
            </template>

            <template #no-data>
                <div class="py-8 text-center text-medium-emphasis">
                    No words yet — add the ones you missed above.
                </div>
            </template>
        </v-data-table>
    </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import Axios from 'axios'
Axios.defaults.baseURL = '/api'
import { SpellingBeeWordRead, fetchSpellingBeeDefinition } from '@/api'
import { formatDate } from '@/spellingBee'

const props = defineProps<{ words?: SpellingBeeWordRead[] }>()

const search = ref('')
const minMisses = ref(1)
const pending = ref(new Set<string>())
// looked up and genuinely not in the dictionary -- don't offer to retry
const notFound = ref(new Set<string>())

const displayCols = ref([
    { key: 'word', title: 'Word' },
    { key: 'times_missed', title: 'Times missed' },
    { key: 'first_missed', title: 'First missed' },
    { key: 'last_missed', title: 'Last missed' },
    { key: 'definition', title: 'Meaning', sortable: false },
])

const filtered = computed(() =>
    (props.words ?? []).filter((w) => w.times_missed >= minMisses.value)
)

// a word you keep missing deserves to stand out more each time
function missColor(times: number) {
    if (times >= 5) return 'error'
    if (times >= 3) return 'warning'
    if (times >= 2) return 'primary'
    return undefined
}

async function lookUp(word: SpellingBeeWordRead) {
    pending.value = new Set(pending.value).add(word.word)
    const result = (await fetchSpellingBeeDefinition(word.word)).data
    if (result.definition) {
        word.definition = result.definition
        word.part_of_speech = result.part_of_speech
    } else {
        notFound.value = new Set(notFound.value).add(word.word)
    }
    const next = new Set(pending.value)
    next.delete(word.word)
    pending.value = next
}
</script>

<style scoped>
.search-field {
    min-width: 240px;
}
</style>
