<template>
    <div>
        <div class="d-flex flex-wrap align-center ga-3 mb-4">
            <v-select
                v-model="selectedDate"
                class="date-select"
                :items="dateItems"
                label="Puzzle"
                hide-details
            ></v-select>
            <v-btn prepend-icon="mdi-shuffle-variant" @click="pickRandomDate">
                Random puzzle
            </v-btn>
        </div>

        <template v-if="hive">
            <v-card border>
                <v-card-text>
                    <div class="text-center mb-2">
                        <!-- .guess reserves its own height, so an empty guess doesn't
                             make the board jump -->
                        <div class="guess" :class="{ 'guess--shake': shaking }">
                            {{ guess }}
                        </div>
                        <div class="text-body-2 text-medium-emphasis" style="min-height: 24px">
                            {{ message }}
                        </div>
                    </div>

                    <spelling-bee-hive
                        :center-letter="hive.center_letter"
                        :outer-letters="shuffled"
                        :size="hexSize"
                        @letter="append"
                    />

                    <div class="d-flex justify-center ga-2 mt-6">
                        <v-btn @click="del">Delete</v-btn>
                        <v-btn icon="mdi-refresh" aria-label="Shuffle" @click="shuffle"></v-btn>
                        <v-btn color="primary" variant="elevated" @click="submit">
                            Enter
                        </v-btn>
                    </div>
                </v-card-text>

                <v-divider />

                <v-card-text>
                    <div class="d-flex align-center justify-space-between mb-2">
                        <span class="text-overline">
                            Found {{ found.length }} of {{ hive.words.length }}
                        </span>
                        <v-btn
                            v-if="found.length < hive.words.length"
                            size="small"
                            variant="text"
                            @click="giveUp"
                        >
                            Give up
                        </v-btn>
                    </div>
                    <v-progress-linear
                        :model-value="(found.length / hive.words.length) * 100"
                        color="primary"
                        rounded
                        height="8"
                        class="mb-4"
                    ></v-progress-linear>

                    <div v-if="found.length" class="d-flex flex-wrap ga-2">
                        <v-chip
                            v-for="word in found"
                            :key="word"
                            size="small"
                            :color="hive.pangrams.includes(word) ? 'secondary' : 'primary'"
                            :prepend-icon="
                                hive.pangrams.includes(word)
                                    ? 'mdi-star-four-points'
                                    : undefined
                            "
                        >
                            {{ word }}
                        </v-chip>
                    </div>
                    <div v-else class="text-body-2 text-medium-emphasis">
                        Type or click the letters to spell a word you missed. Every
                        word uses the center letter.
                    </div>

                    <div v-if="revealed.length" class="mt-4">
                        <div class="text-overline text-medium-emphasis mb-2">
                            Still missed
                        </div>
                        <div class="d-flex flex-wrap ga-2">
                            <v-chip
                                v-for="word in revealed"
                                :key="word"
                                size="small"
                                variant="outlined"
                            >
                                {{ word }}
                            </v-chip>
                        </div>
                    </div>
                </v-card-text>
            </v-card>

            <div v-if="!hive.exact" class="text-body-2 text-medium-emphasis mt-3">
                Letters worked out from your words — usually right, but not certain.
                Record the real ones on the
                <router-link :to="{ name: 'spellingBee' }">missed words</router-link>
                page to make this exact.
            </div>
            <div
                v-for="warning in hive.warnings"
                :key="warning"
                class="text-body-2 text-warning mt-2"
            >
                {{ warning }}
            </div>
        </template>
    </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import SpellingBeeHive from '@/components/SpellingBeeHive.vue'
import { SpellingBeeHiveRead } from '@/api'
import { formatDate } from '@/spellingBee'
import { useDisplay } from 'vuetify'

const props = defineProps<{ hives: SpellingBeeHiveRead[] }>()

const { smAndDown } = useDisplay()
// the board is the whole interface on a phone, so give it the width
const hexSize = computed(() => (smAndDown.value ? 68 : 92))

const selectedDate = ref<string>(props.hives[0]?.puzzle_date ?? '')
const guess = ref('')
const found = ref<string[]>([])
const revealed = ref<string[]>([])
const message = ref('')
const shaking = ref(false)
const shuffled = ref<string[]>([])

const hive = computed(() =>
    props.hives.find((h) => h.puzzle_date === selectedDate.value)
)

const dateItems = computed(() =>
    props.hives.map((h) => ({
        title: `${formatDate(h.puzzle_date)} · ${h.words.length} words`,
        value: h.puzzle_date,
    }))
)

function reset() {
    guess.value = ''
    found.value = []
    revealed.value = []
    message.value = ''
    shuffled.value = hive.value ? [...hive.value.outer_letters] : []
}
watch(hive, reset, { immediate: true })

function pickRandomDate() {
    if (!props.hives.length) return
    const others = props.hives.filter((h) => h.puzzle_date !== selectedDate.value)
    const pool = others.length ? others : props.hives
    selectedDate.value = pool[Math.floor(Math.random() * pool.length)].puzzle_date
}

function append(letter: string) {
    guess.value += letter
}

function del() {
    guess.value = guess.value.slice(0, -1)
}

/** Only the outer letters move — the center stays put, as in the real game. */
function shuffle() {
    const next = [...shuffled.value]
    for (let i = next.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1))
        ;[next[i], next[j]] = [next[j], next[i]]
    }
    shuffled.value = next
}

function reject(text: string) {
    message.value = text
    shaking.value = true
    setTimeout(() => (shaking.value = false), 400)
}

function submit() {
    const word = guess.value
    if (!word || !hive.value) return
    guess.value = ''

    if (found.value.includes(word)) {
        reject('Already found')
    } else if (!hive.value.words.includes(word)) {
        reject('Not one of your missed words')
    } else {
        found.value = [...found.value, word]
        revealed.value = revealed.value.filter((w) => w !== word)
        message.value = hive.value.pangrams.includes(word) ? 'Pangram!' : 'Got it'
    }
}

function giveUp() {
    if (!hive.value) return
    revealed.value = hive.value.words.filter((w) => !found.value.includes(w))
    message.value = ''
}

function onKeydown(e: KeyboardEvent) {
    if (e.metaKey || e.ctrlKey || e.altKey) return
    // don't hijack typing in the puzzle picker
    const tag = (e.target as HTMLElement)?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA') return

    if (e.key === 'Enter') {
        e.preventDefault()
        submit()
    } else if (e.key === 'Backspace') {
        e.preventDefault()
        del()
    } else if (/^[a-zA-Z]$/.test(e.key)) {
        const letter = e.key.toUpperCase()
        if (hive.value && hive.value.outer_letters.concat(hive.value.center_letter).includes(letter)) {
            append(letter)
        }
    }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.date-select {
    max-width: 320px;
}

.guess {
    min-height: 44px;
    font-size: 1.75rem;
    font-weight: 700;
    letter-spacing: 0.08em;
}

.guess--shake {
    animation: shake 0.4s;
}

@keyframes shake {
    0%, 100% { transform: translateX(0); }
    20% { transform: translateX(-8px); }
    40% { transform: translateX(8px); }
    60% { transform: translateX(-5px); }
    80% { transform: translateX(5px); }
}
</style>
