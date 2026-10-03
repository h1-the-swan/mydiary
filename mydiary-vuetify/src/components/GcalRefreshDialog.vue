<template>
    <!-- not dismissable mid-Confirm: the write would still land, unseen by the page -->
    <v-dialog :model-value="true" max-width="900" scrollable :persistent="applying" @update:model-value="close">
        <v-card title="Refresh calendar events">
            <v-card-text>
                <v-progress-linear v-if="loading" indeterminate />
                <v-alert v-else-if="previewError" type="error" variant="tonal" density="compact">
                    {{ previewError }}
                </v-alert>
                <template v-else-if="preview">
                    <v-alert
                        v-if="applyError"
                        :type="applyError.conflict ? 'warning' : 'error'"
                        variant="tonal"
                        density="compact"
                        class="mb-4"
                    >
                        {{ applyError.message }}
                    </v-alert>
                    <p v-if="!preview.changed" class="text-medium-emphasis">
                        Calendar section is already up to date.
                    </p>
                    <template v-else>
                        <p class="text-body-2 text-medium-emphasis mb-3">
                            Confirming replaces the note's Google Calendar events section with this.
                        </p>
                        <div class="diff" role="region" aria-label="Changes to the Google Calendar events section">
                            <div class="diff-lines">
                                <div v-for="(line, i) in preview.diff" :key="i" :class="['diff-line', line.op]">
                                    <span class="gutter" aria-hidden="true">{{ GUTTER[line.op] }}</span>
                                    <span class="sr-only">{{ SPOKEN[line.op] }}</span>
                                    <span class="text">{{ line.text }}</span>
                                </div>
                            </div>
                        </div>
                    </template>
                </template>
            </v-card-text>
            <v-card-actions>
                <v-spacer />
                <v-btn variant="text" :disabled="applying" @click="close">{{ canConfirm ? 'Cancel' : 'Close' }}</v-btn>
                <v-btn v-if="previewError" color="primary" variant="flat" @click="loadPreview">
                    Try again
                </v-btn>
                <v-btn v-else-if="applyError" color="primary" variant="flat" @click="loadPreview">
                    Preview again
                </v-btn>
                <v-btn
                    v-else-if="canConfirm"
                    color="primary"
                    variant="flat"
                    :loading="applying"
                    @click="confirm"
                >
                    Confirm
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { isAxiosError } from 'axios'
import {
    GcalRefreshDiffLineOp,
    GcalRefreshPreviewRead,
    joplinGcalRefresh,
    joplinGcalRefreshPreview,
} from '@/api'
import { detailOf } from '@/util'

const props = defineProps<{ dt: string }>()
const emit = defineEmits<{ close: []; refreshed: [] }>()
// the day the dialog opened on, so a preview and its Confirm can't land on
// different days
const dt = props.dt

const GUTTER: Record<GcalRefreshDiffLineOp, string> = { same: ' ', add: '+', remove: '−' }
const SPOKEN: Record<GcalRefreshDiffLineOp, string> = { same: '', add: 'Added: ', remove: 'Removed: ' }

const loading = ref(false)
const applying = ref(false)
const preview = ref<GcalRefreshPreviewRead>()
const previewError = ref('')
const applyError = ref<{ message: string; conflict: boolean }>()

const canConfirm = computed(() => !!preview.value?.changed && !applyError.value)

async function loadPreview() {
    loading.value = true
    preview.value = undefined
    previewError.value = ''
    applyError.value = undefined
    try {
        preview.value = (await joplinGcalRefreshPreview(dt)).data
    } catch (e) {
        previewError.value = detailOf(e)
    } finally {
        loading.value = false
    }
}

function close() {
    if (!applying.value) emit('close')
}

async function confirm() {
    if (!preview.value || applying.value) return
    applying.value = true
    try {
        await joplinGcalRefresh(dt, {
            before: preview.value.before,
            after: preview.value.after,
        })
        emit('refreshed')
    } catch (e) {
        const status = isAxiosError(e) ? e.response?.status : undefined
        if (status === 409) {
            applyError.value = { message: 'The calendar section changed since this preview.', conflict: true }
        } else if (status === 404 || status === 422 || status === 502) {
            // the backend wrote nothing
            applyError.value = { message: detailOf(e), conflict: false }
        } else {
            applyError.value = {
                message: `Refresh failed (${detailOf(e)}). Preview again to see whether the note changed.`,
                conflict: false,
            }
        }
    } finally {
        applying.value = false
    }
}

onMounted(loadPreview)
</script>

<style scoped>
.diff {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.85rem;
    border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    border-radius: 4px;
    overflow-x: auto;
}
/* as wide as the longest line, so a line's background reaches its end when
   the box scrolls sideways */
.diff-lines {
    width: max-content;
    min-width: 100%;
}
.diff-line {
    display: flex;
    white-space: pre;
    min-height: 1.5em;
    line-height: 1.5em;
}
.diff-line.add {
    background: rgba(var(--v-theme-success), 0.12);
}
.diff-line.remove {
    background: rgba(var(--v-theme-error), 0.12);
}
.gutter {
    flex: none;
    width: 2ch;
    text-align: center;
    user-select: none;
    color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.diff-line.add .gutter {
    color: rgb(var(--v-theme-success));
}
.diff-line.remove .gutter {
    color: rgb(var(--v-theme-error));
}
.text {
    padding-right: 1ch;
}
.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    margin: -1px;
    border: 0;
    overflow: hidden;
    white-space: nowrap;
    clip: rect(0 0 0 0);
}
</style>
