<template>
    <v-card v-if="current" border>
        <v-card-text>
            <div class="d-flex align-center justify-space-between mb-4">
                <span class="text-overline text-medium-emphasis">
                    Missed {{ current.times_missed }}×
                    · last {{ formatDate(current.last_missed) }}
                </span>
                <span class="text-overline text-medium-emphasis">
                    Streak {{ streak }} · {{ correct }}/{{ asked }}
                </span>
            </div>

            <div class="d-flex flex-column flex-sm-row ga-6">
                <div class="flex-grow-1">
                    <div class="mask mb-4">{{ mask }}</div>

                    <div v-if="hintsShown >= 1" class="text-body-2 mb-1">
                        {{ current.word.length }} letters ·
                        {{ distinctCount }} distinct letters
                        <span v-if="current.is_pangram">· it's a pangram</span>
                    </div>
                    <div v-if="hintsShown >= 4" class="text-body-2 mb-1">
                        Letters: {{ scrambled }}
                    </div>
                    <div v-if="hintsShown >= 3" class="text-body-2 mb-1">
                        <span v-if="definition">
                            <span
                                v-if="partOfSpeech"
                                class="text-medium-emphasis font-italic"
                            >
                                {{ partOfSpeech }} —
                            </span>
                            {{ definition }}
                        </span>
                        <span v-else-if="definitionPending" class="text-medium-emphasis">
                            Looking it up…
                        </span>
                        <span v-else class="text-disabled">No definition found</span>
                    </div>

                    <v-text-field
                        ref="answerField"
                        v-model="answer"
                        class="mt-4"
                        label="Your answer"
                        :error-messages="wrong ? 'Not it — try again' : undefined"
                        :success="solved"
                        autocomplete="off"
                        autocapitalize="characters"
                        @keyup.enter="check"
                    ></v-text-field>
                </div>

                <!-- the board the word came from. a word missed on more than one
                     day has more than one, so show each with its date. -->
                <div v-if="currentHives.length" class="hives flex-shrink-0">
                    <div
                        v-for="hive in currentHives"
                        :key="hive.puzzle_date"
                        class="mb-4"
                    >
                        <spelling-bee-hive
                            :center-letter="hive.center_letter"
                            :outer-letters="hive.outer_letters"
                            :size="hiveSize"
                            @letter="appendLetter"
                        />
                        <div class="text-caption text-medium-emphasis text-center mt-1">
                            {{ formatDate(hive.puzzle_date) }}
                            <span v-if="!hive.exact" title="Letters inferred from your words">
                                ·&nbsp;approx
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            <div v-if="solved" class="text-body-2 text-success mb-2">
                {{ current.word }} — got it
                {{ hintsShown ? `with ${hintsShown} hint${hintsShown > 1 ? 's' : ''}` : 'with no hints' }}.
            </div>
            <div v-else-if="gaveUp" class="text-body-2 text-medium-emphasis mb-2">
                It was <strong>{{ current.word }}</strong>.
            </div>
        </v-card-text>

        <v-card-actions>
            <v-btn
                :disabled="hintsShown >= MAX_HINTS || solved || gaveUp"
                prepend-icon="mdi-lightbulb-outline"
                @click="nextHint"
            >
                Hint
            </v-btn>
            <v-btn :disabled="solved || gaveUp" @click="reveal">Give up</v-btn>
            <v-spacer></v-spacer>
            <v-btn
                v-if="solved || gaveUp"
                color="primary"
                variant="elevated"
                @click="nextWord"
            >
                Next word
            </v-btn>
            <v-btn v-else color="primary" variant="elevated" @click="check">
                Check
            </v-btn>
        </v-card-actions>
    </v-card>

    <v-card v-else border>
        <v-card-text class="text-medium-emphasis">
            Nothing to practise yet — add some missed words first.
        </v-card-text>
    </v-card>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import Axios from 'axios'
Axios.defaults.baseURL = '/api'
import SpellingBeeHive from '@/components/SpellingBeeHive.vue'
import {
    SpellingBeeHiveRead,
    SpellingBeeWordRead,
    fetchSpellingBeeDefinition,
} from '@/api'
import { formatDate } from '@/spellingBee'
import { useDisplay } from 'vuetify'

const props = withDefaults(
    defineProps<{
        words: SpellingBeeWordRead[]
        hives?: SpellingBeeHiveRead[]
    }>(),
    { hives: () => [] }
)

const { smAndDown } = useDisplay()
// small enough to sit beside the blanks rather than dominate them
const hiveSize = computed(() => (smAndDown.value ? 46 : 56))

// length/distinct, first letter, first two, definition, scrambled letters
const MAX_HINTS = 5
// don't ask the same handful of words over and over
const RECENT_MEMORY = 5

const current = ref<SpellingBeeWordRead>()
const answer = ref('')
const hintsShown = ref(0)
const solved = ref(false)
const gaveUp = ref(false)
const wrong = ref(false)
const streak = ref(0)
const asked = ref(0)
const correct = ref(0)
const recent = ref<string[]>([])
const definition = ref<string | null>(null)
const partOfSpeech = ref<string | null>(null)
const definitionPending = ref(false)
const answerField = ref()

/**
 * Weighted pick: a word missed five times comes up five times as often as one
 * missed once. That's the whole point — drill what actually needs work.
 */
function pickWord(): SpellingBeeWordRead | undefined {
    if (!props.words.length) return undefined
    let pool = props.words.filter((w) => !recent.value.includes(w.word))
    if (!pool.length) pool = props.words

    const total = pool.reduce((sum, w) => sum + w.times_missed, 0)
    let roll = Math.random() * total
    for (const word of pool) {
        roll -= word.times_missed
        if (roll <= 0) return word
    }
    return pool[pool.length - 1]
}

const distinctCount = computed(() =>
    current.value ? new Set(current.value.word).size : 0
)

/**
 * The board(s) this word was missed on. Seeing the seven letters is the real
 * game's starting position, so it makes the drill a recall exercise rather
 * than a guess. A word missed on several days has several boards.
 */
const currentHives = computed(() => {
    if (!current.value) return []
    const dates = new Set(current.value.misses.map((m) => m.puzzle_date))
    return props.hives.filter((h) => dates.has(h.puzzle_date))
})

function appendLetter(letter: string) {
    if (solved.value || gaveUp.value) return
    answer.value += letter
}

const mask = computed(() => {
    if (!current.value) return ''
    const word = current.value.word
    if (solved.value || gaveUp.value) return word.split('').join(' ')
    // hint 2 reveals the first letter, hint 3 the first two
    const revealCount = hintsShown.value >= 3 ? 2 : hintsShown.value >= 2 ? 1 : 0
    return word
        .split('')
        .map((c, i) => (i < revealCount ? c : '_'))
        .join(' ')
})

const scrambled = computed(() => {
    if (!current.value) return ''
    const letters = current.value.word.split('')
    for (let i = letters.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1))
        ;[letters[i], letters[j]] = [letters[j], letters[i]]
    }
    return letters.join(' ')
})

function nextWord() {
    current.value = pickWord()
    answer.value = ''
    hintsShown.value = 0
    solved.value = false
    gaveUp.value = false
    wrong.value = false
    definition.value = null
    partOfSpeech.value = null
    if (current.value) {
        recent.value = [current.value.word, ...recent.value].slice(0, RECENT_MEMORY)
    }
    nextTick(() => answerField.value?.focus?.())
}

async function nextHint() {
    hintsShown.value += 1
    // the definition hint is the one that needs fetching
    if (hintsShown.value === 3 && current.value && definition.value === null) {
        if (current.value.definition) {
            definition.value = current.value.definition
            partOfSpeech.value = current.value.part_of_speech ?? null
            return
        }
        definitionPending.value = true
        const result = (await fetchSpellingBeeDefinition(current.value.word)).data
        definition.value = result.definition ?? null
        partOfSpeech.value = result.part_of_speech ?? null
        definitionPending.value = false
    }
}

function check() {
    if (!current.value || solved.value || gaveUp.value) return
    const guess = answer.value.trim().toUpperCase()
    if (!guess) return
    if (guess === current.value.word) {
        solved.value = true
        wrong.value = false
        asked.value += 1
        correct.value += 1
        streak.value += 1
    } else {
        wrong.value = true
    }
}

function reveal() {
    if (!current.value) return
    gaveUp.value = true
    wrong.value = false
    asked.value += 1
    streak.value = 0
}

watch(() => props.words, nextWord, { immediate: true })
</script>

<style scoped>
.mask {
    font-size: 1.75rem;
    font-weight: 700;
    letter-spacing: 0.12em;
}

/* wide enough for the board at its largest, so the blanks beside it don't
   reflow as the drill moves between words with one board and several */
.hives {
    width: 188px;
}

@media (max-width: 599px) {
    .hives {
        width: 100%;
    }
}
</style>
