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
                    <div class="mask mb-2">
                        <span
                            v-for="(letter, i) in maskChars"
                            :key="i"
                            class="slot"
                            :class="{ 'slot--blank': !letter }"
                        >
                            {{ letter }}
                        </span>
                    </div>
                    <div class="text-body-2 text-medium-emphasis mb-1">
                        {{ current.word.length }} letters
                    </div>

                    <div v-if="shown.distinct" class="text-body-2 mb-1">
                        {{ distinctCount }} distinct letters<span
                            v-if="current.is_pangram"
                        >
                            — it's a pangram, so it uses all seven</span
                        >
                    </div>
                    <div v-if="shown.scrambled" class="text-body-2 mb-1">
                        Its letters: {{ scrambled }}
                    </div>
                    <div v-if="shown.partOfSpeech || shown.definition" class="text-body-2 mb-1">
                        <span v-if="definitionPending" class="text-medium-emphasis">
                            Looking it up…
                        </span>
                        <template v-else-if="definition || partOfSpeech">
                            <span
                                v-if="partOfSpeech"
                                class="text-medium-emphasis font-italic"
                            >
                                {{ partOfSpeech }}{{ shown.definition ? ' —' : '' }}
                            </span>
                            <span v-if="shown.definition">{{ definition }}</span>
                        </template>
                        <span v-else class="text-disabled">Nothing in the dictionary</span>
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

                    <div class="text-overline text-medium-emphasis">Hints</div>
                    <div class="d-flex flex-wrap ga-2">
                        <v-btn
                            v-for="hint in hintButtons"
                            :key="hint.label"
                            size="small"
                            :prepend-icon="hint.icon"
                            :disabled="hint.done || solved || gaveUp"
                            @click="hint.reveal"
                        >
                            {{ hint.label }}
                        </v-btn>
                    </div>
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
                {{ hintsUsed ? `with ${hintsUsed} hint${hintsUsed > 1 ? 's' : ''}` : 'with no hints' }}.
            </div>
            <div v-else-if="gaveUp" class="text-body-2 text-medium-emphasis mb-2">
                It was <strong>{{ current.word }}</strong>.
            </div>
        </v-card-text>

        <v-card-actions>
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

// don't ask the same handful of words over and over
const RECENT_MEMORY = 5

const current = ref<SpellingBeeWordRead>()
const answer = ref('')
// the first letter is free -- a bare row of blanks is a guess, not recall
const revealedFromStart = ref(1)
const shown = ref({
    lastLetter: false,
    distinct: false,
    partOfSpeech: false,
    definition: false,
    scrambled: false,
})
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

/** One slot per letter; an empty string is a blank still to be worked out. */
const maskChars = computed(() => {
    if (!current.value) return []
    const word = current.value.word
    if (solved.value || gaveUp.value) return word.split('')
    const last = word.length - 1
    return word.split('').map((c, i) => {
        if (i < revealedFromStart.value) return c
        if (shown.value.lastLetter && i === last) return c
        return ''
    })
})

// shuffled once per word rather than per render, so it doesn't dance about
const scrambled = ref('')
function scramble(word: string) {
    const letters = word.split('')
    for (let i = letters.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1))
        ;[letters[i], letters[j]] = [letters[j], letters[i]]
    }
    return letters.join(' ')
}

const hintsUsed = computed(
    () =>
        revealedFromStart.value -
        1 +
        Object.values(shown.value).filter(Boolean).length
)

/** Letters revealed from the left can't finish the word off by themselves. */
const canRevealAnother = computed(
    () => !!current.value && revealedFromStart.value < current.value.word.length - 1
)

const hintButtons = computed(() => [
    {
        label: 'Next letter',
        icon: 'mdi-form-textbox',
        done: !canRevealAnother.value,
        reveal: () => (revealedFromStart.value += 1),
    },
    {
        label: 'Last letter',
        icon: 'mdi-ray-end',
        done: shown.value.lastLetter,
        reveal: () => (shown.value.lastLetter = true),
    },
    {
        label: 'Distinct letters',
        icon: 'mdi-counter',
        done: shown.value.distinct,
        reveal: () => (shown.value.distinct = true),
    },
    {
        label: 'Part of speech',
        icon: 'mdi-tag-outline',
        done: shown.value.partOfSpeech,
        reveal: () => {
            shown.value.partOfSpeech = true
            loadDefinition()
        },
    },
    {
        label: 'Definition',
        icon: 'mdi-book-open-variant',
        done: shown.value.definition,
        reveal: () => {
            shown.value.definition = true
            loadDefinition()
        },
    },
    {
        label: 'Scrambled letters',
        icon: 'mdi-shuffle-variant',
        done: shown.value.scrambled,
        reveal: () => (shown.value.scrambled = true),
    },
])

function nextWord() {
    current.value = pickWord()
    answer.value = ''
    revealedFromStart.value = 1
    shown.value = {
        lastLetter: false,
        distinct: false,
        partOfSpeech: false,
        definition: false,
        scrambled: false,
    }
    solved.value = false
    gaveUp.value = false
    wrong.value = false
    definition.value = null
    partOfSpeech.value = null
    if (current.value) {
        scrambled.value = scramble(current.value.word)
        recent.value = [current.value.word, ...recent.value].slice(0, RECENT_MEMORY)
    }
    nextTick(() => answerField.value?.focus?.())
}

/** Part of speech and definition come from one lookup, so fetch it once. */
async function loadDefinition() {
    if (!current.value || definition.value !== null || definitionPending.value) return
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
    display: flex;
    align-items: flex-end;
    gap: 0.5rem;
    font-size: 1.75rem;
    font-weight: 700;
    /* hug the glyphs, so a blank's rule sits just under the baseline of the
       letters beside it rather than a descender's depth below them */
    line-height: 1;
}

/* fixed-width slots, so the word doesn't shift as letters are filled in */
.slot {
    min-width: 1.1em;
    padding-bottom: 3px;
    border-bottom: 3px solid transparent;
    text-align: center;
}

.slot--blank {
    border-bottom-color: rgba(var(--v-theme-on-surface), 0.3);
}

/* an empty slot has no line box of its own to set the rule's height */
.slot--blank::after {
    content: '\00a0';
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
