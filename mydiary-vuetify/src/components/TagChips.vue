<template>
    <div v-if="editable || (tags && tags.length)" class="tag-chips">
        <div v-if="loading && !tags" class="text-body-2 text-medium-emphasis">
            Loading tags…
        </div>

        <!-- read-only: every tag, linked -->
        <div v-else-if="!editable" class="d-flex flex-wrap align-center ga-2">
            <v-chip
                v-for="tag in tags"
                :key="tag.id"
                :to="tagRoute(tag.key)"
                :prepend-icon="tag.source === 'note' ? 'mdi-text' : undefined"
                :title="chipTitle(tag)"
                variant="tonal"
            >
                #{{ tag.key }}
            </v-chip>
        </div>

        <!-- editable: the note's own tags stay put; the rest can be changed -->
        <div v-else>
            <div v-if="noteTags.length" class="d-flex flex-wrap align-center ga-2 mb-2">
                <v-chip
                    v-for="tag in noteTags"
                    :key="tag.id"
                    :to="tagRoute(tag.key)"
                    prepend-icon="mdi-text"
                    :title="chipTitle(tag)"
                    variant="tonal"
                >
                    #{{ tag.key }}
                </v-chip>
            </div>
            <v-combobox
                v-model="manualKeys"
                :items="suggestions"
                :label="label"
                :loading="saving"
                :error-messages="error"
                placeholder="hiking, or dog:ruffles"
                hint="Enter adds a tag. Tags written in the note itself are shown above and follow the note."
                persistent-hint
                density="compact"
                multiple
                chips
                closable-chips
                clearable
                @update:model-value="onChange"
            >
                <template #chip="{ item, props: chipProps }">
                    <v-chip v-bind="chipProps" :to="tagRoute(keyOf(item))">
                        #{{ keyOf(item) }}
                    </v-chip>
                </template>
            </v-combobox>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { TargetTagRead, readTargetTags, setTargetTags } from '@/api'
import { useAppStore } from '@/store/app'
import { normalizeKey, tagRoute } from '@/tags'

const props = withDefaults(
    defineProps<{
        /** A registry key: "day", "song", "article", "dog", "recipe". */
        targetType: string
        /** The row's id as a string; a date for a day. */
        targetId: string
        /** Show a combobox for the tags that were set by hand. */
        editable?: boolean
        /** Any value; when it changes the tags are fetched again. */
        reloadKey?: unknown
        label?: string
    }>(),
    { editable: false, label: 'Tags' }
)

const app = useAppStore()
const tags = ref<TargetTagRead[]>()
const manualKeys = ref<string[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')

const noteTags = computed(() => (tags.value ?? []).filter((t) => t.source === 'note'))
const suggestions = computed(() =>
    (app.tags ?? []).map((t) => t.key).filter((k) => !noteTags.value.some((t) => t.key === k))
)

// the combobox's chip slot hands over a list item, or the bare string
function keyOf(item: unknown): string {
    if (typeof item === 'string') return item
    return String((item as { value?: unknown } | null)?.value ?? '')
}

function chipTitle(tag: TargetTagRead): string {
    const from = tag.source === 'note' ? 'written in the note' : `added ${tag.source === 'pocket' ? 'with the article' : 'by hand'}`
    return tag.name && tag.name !== tag.slug ? `${tag.name} · ${from}` : from
}

async function load() {
    if (!props.targetId) {
        tags.value = []
        return
    }
    loading.value = true
    try {
        tags.value = (await readTargetTags(props.targetType, props.targetId)).data
        manualKeys.value = tags.value.filter((t) => t.source !== 'note').map((t) => t.key)
    } finally {
        loading.value = false
    }
    if (props.editable && !app.tags) app.loadTags()
}

async function onChange(values: unknown) {
    // the combobox hands back whatever was typed; normalise it the way the
    // backend would, and drop anything that is not a tag
    const keys = Array.from(
        new Set(
            ((values as unknown[]) ?? [])
                .map((v) => (typeof v === 'string' ? normalizeKey(v) : null))
                .filter((k): k is string => !!k)
        )
    )
    manualKeys.value = keys
    saving.value = true
    error.value = ''
    try {
        tags.value = (await setTargetTags(props.targetType, props.targetId, keys)).data
        manualKeys.value = tags.value.filter((t) => t.source !== 'note').map((t) => t.key)
        app.loadTags()
    } catch (e: any) {
        error.value = e?.response?.data?.detail ?? 'Could not save tags'
    } finally {
        saving.value = false
    }
}

watch(() => [props.targetType, props.targetId, props.reloadKey], load, { immediate: true })
</script>
