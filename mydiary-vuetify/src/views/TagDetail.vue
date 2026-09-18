<template>
    <page-shell :eyebrow="eyebrow">
        <template #title>
            <span v-if="tag">#{{ tag.key }}</span>
            <span v-else-if="notFound">Tag not found</span>
            <span v-else>Loading…</span>
        </template>
        <template #actions>
            <v-btn size="small" variant="text" :to="{ name: 'tags' }" prepend-icon="mdi-arrow-left">
                All tags
            </v-btn>
            <template v-if="tag">
                <v-btn size="small" prepend-icon="mdi-pencil" @click="openRename">Rename</v-btn>
                <v-btn size="small" color="error" prepend-icon="mdi-delete" @click="confirmDelete = true">
                    Delete
                </v-btn>
            </template>
        </template>

        <div v-if="notFound" class="reading text-medium-emphasis">
            There is no tag called <code>#{{ tagKey }}</code>.
        </div>

        <template v-else-if="tag">
            <div v-if="tag.resolved" class="reading mb-8">
                <section-header label="Refers to" />
                <v-card border>
                    <v-card-item>
                        <template #prepend>
                            <v-icon icon="mdi-link-variant" />
                        </template>
                        <v-card-title>
                            <router-link v-if="resolvedRoute" :to="resolvedRoute">
                                {{ tag.resolved.label }}
                            </router-link>
                            <span v-else>{{ tag.resolved.label }}</span>
                        </v-card-title>
                        <v-card-subtitle>
                            {{ kindLabel(tag.resolved.kind) }}
                        </v-card-subtitle>
                    </v-card-item>
                </v-card>
            </div>

            <div v-if="!tag.targets?.length" class="reading text-medium-emphasis">
                Nothing carries this tag yet.
            </div>

            <section v-for="group in groups" :key="group.kind" class="reading mb-8">
                <section-header :label="group.plural" :meta="String(group.refs.length)" />
                <div class="d-flex flex-wrap ga-2">
                    <v-chip
                        v-for="ref in group.refs"
                        :key="`${ref.kind}-${ref.id}`"
                        :to="targetRoute(ref.kind, ref.id, ref.frontend_route)"
                        :prepend-icon="ref.source === 'note' ? 'mdi-text' : undefined"
                        :variant="targetRoute(ref.kind, ref.id, ref.frontend_route) ? 'tonal' : 'outlined'"
                        :title="ref.source === 'note' ? 'written in the note' : undefined"
                    >
                        {{ ref.kind === 'day' ? formatDay(ref.id) : ref.label }}
                    </v-chip>
                </div>
            </section>
        </template>

        <v-dialog v-model="renaming" max-width="480">
            <v-card title="Rename tag">
                <v-card-text>
                    <v-text-field v-model="form.name" label="Label" hint="How the tag is shown" persistent-hint class="mb-4" />
                    <v-text-field v-model="form.namespace" label="Namespace" hint="Optional, e.g. dog" persistent-hint class="mb-4" />
                    <v-text-field v-model="form.slug" label="Slug" hint="e.g. ruffles" persistent-hint />
                    <p v-if="renameError" class="text-error mt-4 mb-0">{{ renameError }}</p>
                </v-card-text>
                <v-card-actions>
                    <v-btn color="primary" variant="elevated" :loading="busy" @click="onRename">Save</v-btn>
                    <v-btn @click="renaming = false">Cancel</v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

        <v-dialog v-model="confirmDelete" max-width="480">
            <v-card title="Delete this tag?">
                <v-card-text>
                    <code>#{{ tag?.key }}</code> comes off everything it is on
                    ({{ targetCount }} {{ targetCount === 1 ? 'thing' : 'things' }}).
                    A note that still spells it out will bring it back on the next sync.
                </v-card-text>
                <v-card-actions>
                    <v-btn color="error" variant="elevated" :loading="busy" @click="onDelete">Delete</v-btn>
                    <v-btn @click="confirmDelete = false">Cancel</v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </page-shell>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { TagDetailRead, TargetRefRead, deleteTag, readTagByKey, updateTag } from '@/api'
import PageShell from '@/components/PageShell.vue'
import SectionHeader from '@/components/SectionHeader.vue'
import { useAppStore } from '@/store/app'
import { formatDay, namespaceLabels, targetRoute } from '@/tags'
axios.defaults.baseURL = '/api'

const props = defineProps<{ tagKey: string }>()
const router = useRouter()
const app = useAppStore()

const tag = ref<TagDetailRead>()
const notFound = ref(false)
const busy = ref(false)
const renaming = ref(false)
const renameError = ref('')
const confirmDelete = ref(false)
const form = reactive({ name: '', namespace: '', slug: '' })

const eyebrow = computed(() => {
    if (!tag.value) return 'Tag'
    const { label } = namespaceLabels(tag.value.namespace ?? '', app.tagNamespaces)
    const shownName = tag.value.name !== tag.value.slug ? tag.value.name : ''
    return shownName ? `${label} · ${shownName}` : label
})

const targetCount = computed(() => tag.value?.targets?.length ?? 0)

const resolvedRoute = computed(() =>
    tag.value?.resolved
        ? targetRoute(tag.value.resolved.kind, tag.value.resolved.id, tag.value.resolved.frontend_route)
        : undefined
)

function kindLabel(kind: string): string {
    return namespaceLabels(kind, app.tagNamespaces).label
}

const groups = computed(() => {
    const out: { kind: string; plural: string; refs: TargetRefRead[] }[] = []
    for (const ref of tag.value?.targets ?? []) {
        let group = out.find((g) => g.kind === ref.kind)
        if (!group) {
            group = { kind: ref.kind, plural: namespaceLabels(ref.kind, app.tagNamespaces).plural, refs: [] }
            out.push(group)
        }
        group.refs.push(ref)
    }
    return out
})

async function load() {
    tag.value = undefined
    notFound.value = false
    try {
        tag.value = (await readTagByKey({ key: props.tagKey })).data
    } catch (e: any) {
        if (e?.response?.status === 404) notFound.value = true
        else throw e
    }
    if (!app.tagNamespaces) app.loadTagNamespaces()
}

function openRename() {
    if (!tag.value) return
    form.name = tag.value.name
    form.namespace = tag.value.namespace ?? ''
    form.slug = tag.value.slug
    renameError.value = ''
    renaming.value = true
}

async function onRename() {
    if (!tag.value) return
    busy.value = true
    renameError.value = ''
    try {
        const updated = (await updateTag(tag.value.id, { name: form.name, namespace: form.namespace, slug: form.slug })).data
        renaming.value = false
        app.loadTags()
        if (updated.key !== props.tagKey) {
            router.replace({ name: 'tag', params: { tagKey: updated.key } })
        } else {
            await load()
        }
    } catch (e: any) {
        renameError.value = e?.response?.data?.detail ?? 'Could not rename the tag'
    } finally {
        busy.value = false
    }
}

async function onDelete() {
    if (!tag.value) return
    busy.value = true
    try {
        await deleteTag(tag.value.id)
        confirmDelete.value = false
        app.loadTags()
        router.push({ name: 'tags' })
    } finally {
        busy.value = false
    }
}

watch(() => props.tagKey, load, { immediate: true })
</script>
