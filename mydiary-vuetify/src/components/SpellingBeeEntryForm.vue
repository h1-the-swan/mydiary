<template>
    <v-card border>
        <v-form @submit.prevent="onSave">
            <v-card-text>
                <div class="d-flex flex-column flex-sm-row ga-4 mb-4">
                    <v-date-input
                        v-model="puzzleDate"
                        class="flex-grow-0 date-field"
                        label="Puzzle date"
                        prepend-icon=""
                        prepend-inner-icon="$calendar"
                        hide-details
                    ></v-date-input>
                </div>

                <v-textarea
                    v-model="raw"
                    label="Missed words"
                    rows="4"
                    auto-grow
                    hint="Paste the answers you didn't get — one per line, or separated by spaces or commas"
                    persistent-hint
                ></v-textarea>

                <div v-if="parsed.length" class="mt-4">
                    <div class="d-flex flex-wrap ga-2 mb-3">
                        <v-chip
                            v-for="word in parsed"
                            :key="word"
                            size="small"
                            closable
                            :color="chipColor(word)"
                            :prepend-icon="
                                isPangram(word) ? 'mdi-star-four-points' : undefined
                            "
                            @click:close="removeWord(word)"
                        >
                            {{ word }}
                        </v-chip>
                    </div>

                    <div
                        class="text-body-2"
                        :class="
                            tooManyLetters ? 'text-warning' : 'text-medium-emphasis'
                        "
                    >
                        {{ summary }}
                    </div>
                    <div v-if="tooManyLetters" class="text-body-2 text-warning">
                        A Spelling Bee puzzle only has {{ HIVE_SIZE }} letters, so
                        something here is probably a typo or from another day.
                    </div>
                    <div v-if="alreadyRecorded.length" class="text-body-2 text-medium-emphasis">
                        {{ alreadyRecorded.length }} already recorded for this date.
                    </div>
                </div>

                <v-expansion-panels v-if="parsed.length" class="mt-4" variant="accordion">
                    <v-expansion-panel>
                        <v-expansion-panel-title>
                            Puzzle letters (optional)
                        </v-expansion-panel-title>
                        <v-expansion-panel-text>
                            <p class="text-body-2 text-medium-emphasis mb-4">
                                Type all seven letters, <strong>center letter
                                first</strong>. Without them the hive is worked out
                                from your words, which is usually right — recording
                                them makes it exact.
                            </p>
                            <div class="d-flex flex-wrap align-center ga-4">
                                <v-text-field
                                    v-model="letterInput"
                                    class="letters-field"
                                    label="Seven letters"
                                    maxlength="7"
                                    hide-details
                                ></v-text-field>
                                <!-- an <input> can't bold one character, so the
                                     parsed letters are echoed back instead -->
                                <div v-if="puzzleLetters" class="letter-preview">
                                    <span class="letter-preview__center">
                                        {{ puzzleLetters[0] }}
                                    </span>
                                    <span
                                        v-for="(letter, i) in puzzleLetters.slice(1)"
                                        :key="`${letter}-${i}`"
                                    >
                                        {{ letter }}
                                    </span>
                                </div>
                            </div>
                            <div
                                v-if="puzzleLetters"
                                class="text-body-2 text-medium-emphasis mt-2"
                            >
                                Center letter
                                <strong>{{ puzzleLetters[0] }}</strong> — every
                                answer has to use it.
                            </div>
                            <div v-if="letterError" class="text-body-2 text-warning mt-2">
                                {{ letterError }}
                            </div>
                        </v-expansion-panel-text>
                    </v-expansion-panel>
                </v-expansion-panels>
            </v-card-text>

            <v-card-actions>
                <v-spacer></v-spacer>
                <v-btn
                    color="primary"
                    variant="elevated"
                    type="submit"
                    :disabled="!parsed.length || saving || !!letterError"
                    :loading="saving"
                >
                    Add {{ parsed.length || '' }}
                    {{ parsed.length === 1 ? 'word' : 'words' }}
                </v-btn>
            </v-card-actions>
        </v-form>

        <v-snackbar v-model="snackbar" :timeout="4000">
            {{ snackbarText }}
            <template #actions>
                <v-btn variant="text" @click="snackbar = false">Close</v-btn>
            </template>
        </v-snackbar>
    </v-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Axios from 'axios'
Axios.defaults.baseURL = '/api'
import {
    createSpellingBeeMisses,
    readSpellingBeeMissesList,
    upsertSpellingBeePuzzle,
} from '@/api'
import {
    HIVE_SIZE,
    MIN_WORD_LEN,
    distinctLetters,
    isPangram,
    isoDate,
    normalizeWord,
    parseWords,
    yesterday,
} from '@/spellingBee'

const emit = defineEmits<{ saved: [] }>()

const puzzleDate = ref<Date>(yesterday())
const raw = ref('')
// all seven at once, center letter first
const letterInput = ref('')
const saving = ref(false)
const snackbar = ref(false)
const snackbarText = ref('')
// what's already stored for the selected date, so the form can say so up front
const alreadyRecorded = ref<string[]>([])

const parsed = computed(() => parseWords(raw.value))
const tooShort = computed(() =>
    parsed.value.filter((w) => w.length < MIN_WORD_LEN)
)
const letters = computed(() => distinctLetters(parsed.value))
const tooManyLetters = computed(() => letters.value.size > HIVE_SIZE)
const pangrams = computed(() => parsed.value.filter(isPangram))

const summary = computed(() => {
    const parts = [
        `${parsed.value.length} ${parsed.value.length === 1 ? 'word' : 'words'}`,
        `${letters.value.size} distinct letters`,
    ]
    if (pangrams.value.length) {
        parts.push(
            `${pangrams.value.length} pangram${pangrams.value.length > 1 ? 's' : ''}`
        )
    }
    if (tooShort.value.length) {
        parts.push(`${tooShort.value.length} too short to count`)
    }
    return parts.join(' · ')
})

const puzzleLetters = computed(() => normalizeWord(letterInput.value))

const letterError = computed(() => {
    const value = puzzleLetters.value
    if (!value) return ''
    if (value.length !== HIVE_SIZE) {
        return `Give all ${HIVE_SIZE} letters, center letter first.`
    }
    if (new Set(value).size !== HIVE_SIZE) {
        return 'The seven letters must all be different.'
    }
    return ''
})

const lettersReady = computed(
    () => puzzleLetters.value.length === HIVE_SIZE && !letterError.value
)

function chipColor(word: string) {
    if (word.length < MIN_WORD_LEN) return 'warning'
    if (alreadyRecorded.value.includes(word)) return undefined
    if (isPangram(word)) return 'secondary'
    return 'primary'
}

function removeWord(word: string) {
    raw.value = parsed.value.filter((w) => w !== word).join('\n')
}

async function loadExisting() {
    alreadyRecorded.value = await readSpellingBeeMissesList({
        puzzle_date: isoDate(puzzleDate.value),
    }).then((res) => res.data.map((m) => m.word))
}
watch(puzzleDate, loadExisting, { immediate: true })

async function onSave() {
    if (!parsed.value.length) return
    saving.value = true
    const dt = isoDate(puzzleDate.value)
    const result = (
        await createSpellingBeeMisses({
            puzzle_date: dt,
            words: parsed.value,
        })
    ).data

    // the first letter typed is the center one; the rest are the outer six
    if (lettersReady.value) {
        await upsertSpellingBeePuzzle(dt, {
            center_letter: puzzleLetters.value[0],
            outer_letters: puzzleLetters.value.slice(1),
        })
    }

    const bits = [`Added ${result.created.length}`]
    if (result.skipped.length) bits.push(`${result.skipped.length} already recorded`)
    if (result.invalid.length) bits.push(`${result.invalid.length} too short`)
    snackbarText.value = `${bits.join(' · ')}.`
    snackbar.value = true

    raw.value = ''
    letterInput.value = ''
    saving.value = false
    await loadExisting()
    emit('saved')
}
</script>

<style scoped>
.date-field {
    min-width: 220px;
}

.letters-field {
    max-width: 220px;
}

/* echoes back what was typed, so the center letter is visibly the first one */
.letter-preview {
    display: flex;
    gap: 0.5rem;
    font-size: 1.25rem;
    font-weight: 400;
    letter-spacing: 0.08em;
    color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}

.letter-preview__center {
    font-weight: 800;
    color: rgb(var(--v-theme-primary));
}
</style>
