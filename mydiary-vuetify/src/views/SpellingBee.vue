<template>
    <page-shell eyebrow="Spelling Bee" title="Missed words">
        <template #actions>
            <v-btn
                :to="{ name: 'spellingBeePractice' }"
                prepend-icon="mdi-gamepad-variant"
            >
                Practice
            </v-btn>
        </template>

        <section class="reading mb-10">
            <section-header label="Add missed words" />
            <spelling-bee-entry-form @saved="app.loadSpellingBeeWords()" />
        </section>

        <section>
            <section-header label="Words you keep missing" :meta="wordCountLabel" />
            <spelling-bee-word-table :words="app.spellingBeeWords" />
        </section>
    </page-shell>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import PageShell from '@/components/PageShell.vue'
import SectionHeader from '@/components/SectionHeader.vue'
import SpellingBeeEntryForm from '@/components/SpellingBeeEntryForm.vue'
import SpellingBeeWordTable from '@/components/SpellingBeeWordTable.vue'
import { useAppStore } from '@/store/app'

const app = useAppStore()

const wordCountLabel = computed<string>(() => {
    const words = app.spellingBeeWords
    if (!words) return ''
    const repeat = words.filter((w) => w.times_missed > 1).length
    return repeat ? `${words.length} · ${repeat} more than once` : `${words.length}`
})

onMounted(async () => {
    await app.loadSpellingBeeWords()
})
</script>
