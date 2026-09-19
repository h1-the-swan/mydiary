<template>
    <v-bottom-sheet :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)">
        <v-card class="pa-4">
            <div class="text-subtitle-1 font-weight-medium">How did that go?</div>
            <div class="text-body-2 text-medium-emphasis mb-3">
                Tap a section you stumbled on. Tap it again if you didn't play it.
            </div>
            <div class="d-flex flex-wrap ga-2 mb-4">
                <v-chip
                    v-for="key in sectionKeys"
                    :key="key"
                    size="large"
                    :color="STATE_COLOR[states[key]]"
                    :variant="states[key] === 'skipped' ? 'outlined' : 'flat'"
                    :prepend-icon="STATE_ICON[states[key]]"
                    @click="states[key] = NEXT[states[key]]"
                >
                    {{ key }}
                </v-chip>
            </div>
            <v-text-field v-model="note" label="Note (optional)" hide-details class="mb-4" />
            <div class="d-flex ga-2 justify-end">
                <v-btn variant="text" @click="emit('update:modelValue', false)">Cancel</v-btn>
                <v-btn color="primary" variant="flat" :disabled="!played.length" @click="save">
                    Save
                </v-btn>
            </div>
        </v-card>
    </v-bottom-sheet>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

type State = 'clean' | 'stumbled' | 'skipped'
const NEXT: Record<State, State> = { clean: 'stumbled', stumbled: 'skipped', skipped: 'clean' }
const STATE_COLOR: Record<State, string | undefined> = { clean: 'success', stumbled: 'warning', skipped: undefined }
const STATE_ICON: Record<State, string> = {
    clean: 'mdi-check',
    stumbled: 'mdi-alert-circle-outline',
    skipped: 'mdi-minus',
}

const props = defineProps<{ modelValue: boolean; sectionKeys: string[] }>()
const emit = defineEmits<{
    'update:modelValue': [open: boolean]
    save: [run: { sections: { section_key: string; stumbled: boolean }[]; note: string }]
}>()

const states = ref<Record<string, State>>({})
const note = ref('')

// every section starts clean, so a clean run of the whole song is Done, then Save
watch(
    () => props.modelValue,
    (open) => {
        if (!open) return
        states.value = Object.fromEntries(props.sectionKeys.map((k) => [k, 'clean' as State]))
        note.value = ''
    }
)

const played = computed(() => props.sectionKeys.filter((k) => states.value[k] !== 'skipped'))

function save() {
    emit('save', {
        sections: played.value.map((k) => ({ section_key: k, stumbled: states.value[k] === 'stumbled' })),
        note: note.value.trim(),
    })
    emit('update:modelValue', false)
}
</script>
