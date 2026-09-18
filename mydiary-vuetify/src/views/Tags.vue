<template>
    <page-shell title="Tags">
        <template #actions>
            <v-text-field
                v-model="search"
                class="tags-search"
                label="Filter"
                prepend-inner-icon="mdi-magnify"
                density="compact"
                hide-details
                single-line
                clearable
            />
            <v-btn size="small" prepend-icon="mdi-sync" :loading="syncing" @click="onSync">
                Sync from Joplin
            </v-btn>
        </template>

        <v-progress-linear v-if="!app.tags || !app.tagNamespaces" indeterminate />

        <div v-else-if="!app.tags.length" class="reading text-body-1 text-medium-emphasis">
            No tags yet. Write <code>#hiking</code> or <code>#dog:ruffles</code> in a diary
            note, or add tags to a day or a song, and they show up here.
        </div>

        <template v-else>
            <section v-for="group in groups" :key="group.namespace" class="mb-8">
                <section-header :label="group.label" :meta="String(group.tags.length)" />
                <div class="d-flex flex-wrap ga-2">
                    <v-chip
                        v-for="tag in group.tags"
                        :key="tag.id"
                        :to="tagRoute(tag.key)"
                        :title="tag.name !== tag.slug ? tag.name : undefined"
                        variant="tonal"
                    >
                        #{{ tag.key }}
                        <span class="ml-1 text-medium-emphasis">{{ tag.num_links ?? 0 }}</span>
                    </v-chip>
                </div>
            </section>
            <p v-if="search && !groups.length" class="text-medium-emphasis">
                No tags match “{{ search }}”.
            </p>
        </template>

        <v-snackbar v-model="snackbar">
            {{ snackbarText }}
            <template v-slot:actions>
                <v-btn variant="text" @click="snackbar = false">Close</v-btn>
            </template>
        </v-snackbar>
    </page-shell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { TagRead, readTagSyncStatus, syncTags } from '@/api'
import PageShell from '@/components/PageShell.vue'
import SectionHeader from '@/components/SectionHeader.vue'
import { useAppStore } from '@/store/app'
import { namespaceSectionLabel, tagRoute } from '@/tags'
axios.defaults.baseURL = '/api'

const app = useAppStore()
const search = ref('')
const syncing = ref(false)
const snackbar = ref(false)
const snackbarText = ref('')

const groups = computed(() => {
    const needle = (search.value || '').trim().toLowerCase()
    const byNamespace = new Map<string, TagRead[]>()
    for (const tag of app.tags ?? []) {
        if (needle && !`${tag.key} ${tag.name}`.toLowerCase().includes(needle)) continue
        const list = byNamespace.get(tag.namespace ?? '') ?? []
        list.push(tag)
        byNamespace.set(tag.namespace ?? '', list)
    }
    // the backend orders namespaces with "" first; keep that
    return Array.from(byNamespace.entries()).map(([namespace, tags]) => ({
        namespace,
        label: namespaceSectionLabel(namespace, app.tagNamespaces),
        tags,
    }))
})

const POLL_MS = 1500
const POLL_LIMIT_MS = 10 * 60 * 1000

function sleep(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * The all-notes sync runs in the background on the server, so the request
 * returns at once. Poll its status until it finishes, then reload the tags,
 * so what was just written in Joplin shows up without a page refresh.
 */
async function onSync() {
    syncing.value = true
    try {
        await syncTags()
    } catch {
        snackbarText.value = 'Could not start the sync. Is Joplin running?'
        snackbar.value = true
        syncing.value = false
        return
    }
    const deadline = Date.now() + POLL_LIMIT_MS
    try {
        while (Date.now() < deadline) {
            await sleep(POLL_MS)
            const status = (await readTagSyncStatus()).data
            if (status.running) continue
            await Promise.all([app.loadTags(), app.loadTagNamespaces()])
            if (status.error) {
                snackbarText.value = `Sync failed: ${status.error}`
            } else if (status.last) {
                const { notes_checked, notes_synced, tags_added, tags_removed } = status.last
                snackbarText.value =
                    `Checked ${notes_checked} notes, fetched ${notes_synced}. ` +
                    `${tags_added} tag${tags_added === 1 ? '' : 's'} added, ${tags_removed} removed.`
            } else {
                snackbarText.value = 'Sync finished.'
            }
            return
        }
        snackbarText.value = 'The sync is still running. Reload the page later to see its tags.'
    } catch {
        snackbarText.value = 'Lost track of the sync. Reload the page to see its tags.'
    } finally {
        syncing.value = false
        snackbar.value = true
    }
}

onMounted(() => {
    app.loadTags()
    app.loadTagNamespaces()
})
</script>

<style scoped>
.tags-search {
    min-width: 220px;
}
</style>
