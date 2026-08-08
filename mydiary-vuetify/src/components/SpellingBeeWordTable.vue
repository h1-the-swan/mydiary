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
                    <td class="text-right">
                        <v-btn
                            icon="mdi-close"
                            size="small"
                            variant="text"
                            density="comfortable"
                            :aria-label="`Remove ${item.word}`"
                            @click="startRemove(item)"
                        ></v-btn>
                    </td>
                </tr>
            </template>

            <template #no-data>
                <div class="py-8 text-center text-medium-emphasis">
                    No words yet — add the ones you missed above.
                </div>
            </template>
        </v-data-table>

        <!-- a word missed on several days needs to say WHICH day to forget -->
        <v-dialog v-model="removeDialog" max-width="460">
            <v-card v-if="removing">
                <v-card-title>Remove {{ removing.word }}?</v-card-title>

                <!-- one occurrence is unambiguous, so just confirm it -->
                <v-card-text v-if="removing.times_missed === 1">
                    <p class="text-body-2 text-medium-emphasis">
                        Missed on {{ formatDate(removing.misses[0].puzzle_date) }}.
                        This takes it off your list.
                    </p>
                </v-card-text>

                <!-- several means the word has a history: ask which day to forget -->
                <v-card-text v-else>
                    <p class="text-body-2 text-medium-emphasis mb-4">
                        You missed this on {{ removing.times_missed }} days. Pick the
                        ones to forget.
                    </p>
                    <v-checkbox
                        v-for="miss in removing.misses"
                        :key="miss.id"
                        v-model="selectedIds"
                        :value="miss.id"
                        :label="formatDate(miss.puzzle_date)"
                        density="compact"
                        hide-details
                    ></v-checkbox>
                </v-card-text>

                <v-card-actions>
                    <v-btn
                        v-if="removing.times_missed > 1"
                        variant="text"
                        @click="selectedIds = allIds"
                    >
                        Select all
                    </v-btn>
                    <v-spacer></v-spacer>
                    <v-btn variant="text" @click="removeDialog = false">Cancel</v-btn>
                    <v-btn
                        color="error"
                        variant="elevated"
                        :disabled="!selectedIds.length"
                        :loading="deleting"
                        @click="confirmRemove"
                    >
                        {{ removeLabel }}
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import Axios from 'axios'
Axios.defaults.baseURL = '/api'
import {
    SpellingBeeWordRead,
    deleteSpellingBeeMiss,
    fetchSpellingBeeDefinition,
} from '@/api'
import { formatDate } from '@/spellingBee'

const props = defineProps<{ words?: SpellingBeeWordRead[] }>()
const emit = defineEmits<{ removed: [] }>()

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
    { key: 'remove', title: '', sortable: false, width: 56 },
])

const removeDialog = ref(false)
const removing = ref<SpellingBeeWordRead>()
const selectedIds = ref<number[]>([])
const deleting = ref(false)

const allIds = computed(() => removing.value?.misses.map((m) => m.id) ?? [])

const removeLabel = computed(() => {
    if (removing.value?.times_missed === 1) return 'Remove'
    return selectedIds.value.length
        ? `Remove ${selectedIds.value.length}`
        : 'Remove'
})

/**
 * Always confirm -- a removal isn't undoable. A word missed once just needs a
 * yes; several means the word has a history, and forgetting the wrong day
 * would quietly corrupt the counts, so ask which.
 */
function startRemove(word: SpellingBeeWordRead) {
    removing.value = word
    // a single occurrence has nothing to choose between, so it's pre-selected
    selectedIds.value = word.times_missed === 1 ? [word.misses[0].id] : []
    removeDialog.value = true
}

async function confirmRemove() {
    deleting.value = true
    for (const id of selectedIds.value) {
        await deleteSpellingBeeMiss(id)
    }
    deleting.value = false
    removeDialog.value = false
    emit('removed')
}

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
