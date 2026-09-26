<template>
    <v-card>
        <v-form>
            <v-card-title>
                <span class="text-h6">{{ formTitle }}</span>
            </v-card-title>

            <v-card-text>
                <v-container class="pa-0">
                    <v-row>
                        <v-col cols="12">
                            <!-- results come filtered from Spotify, hence no-filter -->
                            <v-autocomplete
                                v-model="picked"
                                :search="searchText"
                                @update:search="searchText = $event"
                                :items="searchResults"
                                :loading="searching"
                                :error-messages="searchError"
                                item-title="name"
                                item-value="spotify_id"
                                label="Find on Spotify"
                                prepend-inner-icon="mdi-magnify"
                                return-object
                                no-filter
                                clearable
                                :hide-no-data="searchText.trim().length < 2"
                                :no-data-text="searching ? 'Searching…' : 'No tracks found'"
                                @update:model-value="onPick"
                            >
                                <template #item="{ props: itemProps, item }">
                                    <v-list-item
                                        v-bind="itemProps"
                                        :title="item.name"
                                        :subtitle="trackSubtitle(item)"
                                    >
                                        <template #prepend>
                                            <v-avatar rounded="0" size="40">
                                                <v-img
                                                    v-if="item.thumbnail_url"
                                                    :src="item.thumbnail_url"
                                                />
                                                <v-icon v-else icon="mdi-music" />
                                            </v-avatar>
                                        </template>
                                        <template v-if="usedByOther(item) !== null" #append>
                                            <v-chip size="x-small" color="warning">
                                                already in your songs
                                            </v-chip>
                                        </template>
                                    </v-list-item>
                                </template>
                            </v-autocomplete>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.name"
                                label="Name"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.artist_name"
                                label="Artist"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-checkbox
                                v-model="submitPerformSong.learned"
                                label="Learned"
                                hint="Unticked songs are in the learning queue"
                                persistent-hint
                            ></v-checkbox>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.spotify_id"
                                label="Spotify ID"
                                :hint="
                                    spotifyNote
                                        ? undefined
                                        : 'Paste an ID or link to fill Name and Artist'
                                "
                                :loading="spotifyLoading"
                                :error-messages="spotifyError"
                                :messages="spotifyNote"
                                @paste="onSpotifyPaste"
                                @blur="lookupSpotify(submitPerformSong.spotify_id)"
                            ></v-text-field>
                        </v-col>
                        <v-col v-if="usedBy" cols="12">
                            <v-alert type="warning" variant="tonal" density="compact">
                                This recording is already used by
                                <router-link
                                    :to="{ name: 'performSong', params: { id: usedBy.id } }"
                                    >{{ usedBy.name }}</router-link
                                >. You can still save.
                            </v-alert>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.notes"
                                label="Notes"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.perform_url"
                                label="Performance URL"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.created_at"
                                label="Added"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.key"
                                label="Key"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.capo"
                                label="Capo"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.lyrics"
                                label="Lyrics"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.learned_dt"
                                label="Learned on"
                            ></v-text-field>
                        </v-col>
                        <v-col v-if="props.performSong" cols="12">
                            <!-- saved as you go, separately from the form -->
                            <tag-chips
                                target-type="song"
                                :target-id="String(props.performSong.id)"
                                editable
                            />
                        </v-col>
                    </v-row>
                </v-container>
            </v-card-text>
            <v-card-actions>
                <v-btn color="primary" variant="elevated" @click="onSave">
                    Save
                </v-btn>
                <v-spacer />
                <v-btn
                    color="error"
                    variant="text"
                    disabled
                    title="Deleting songs is not enabled"
                    @click="onDelete"
                >
                    Delete
                </v-btn>
            </v-card-actions>
        </v-form>
        <v-snackbar v-if="submitted" v-model="snackbar">
            Saved “{{ submitted.name }}”.
            <template v-slot:actions>
                <v-btn variant="text" @click="snackbar = false">
                    Close
                </v-btn>
            </template>
        </v-snackbar>
    </v-card>
</template>

<script lang="ts" setup>
import { computed } from 'vue'
import { watch, watchEffect } from 'vue'
import { PerformSongUpdate } from '@/api'
import { ref } from 'vue'
import { useDate } from 'vuetify'
import {
    PerformSongRead,
    updatePerformSong,
    createPerformSong,
    PerformSongCreate,
    deletePerformSong,
    lookupSpotifyTrack,
    searchSpotifyTracks,
    TrackSummaryRead,
} from '@/api'
import { isAxiosError } from 'axios'
import { useAppStore } from '@/store/app'
import TagChips from '@/components/TagChips.vue'
import { useRouter } from 'vue-router'
const date = useDate()
const props = defineProps<{
    performSong?: PerformSongRead
}>()
const router = useRouter()
const app = useAppStore()
// a new song is usually one about to be learned, so it starts in the queue
const submitPerformSong = ref<PerformSongUpdate>(props.performSong ? {} : { learned: false })
const submitted = ref<PerformSongRead>()
const snackbar = ref(false)
const formTitle = computed(() => {
    if (props.performSong) {
        return 'Edit song'
    } else {
        return 'Add a song'
    }
})
function dateFmt(dateStr: string | null | undefined) {
    if (!dateStr) return
    return new Date(dateStr).toISOString().substring(0, 10)
}
async function onSave() {
    if (!submitPerformSong.value.name) throw Error
    if (submitPerformSong.value.created_at) {
        submitPerformSong.value.created_at = new Date(
            submitPerformSong.value.created_at
        ).toISOString()
    } else {
        submitPerformSong.value.created_at = new Date().toISOString()
    }
    if (submitPerformSong.value.learned_dt) {
        submitPerformSong.value.learned_dt = new Date(
            submitPerformSong.value.learned_dt
        ).toISOString()
    }
    // the backend normalizes the Spotify ID and rejects one Spotify doesn't know
    try {
        if (!props.performSong) {
            submitted.value = (
                await createPerformSong(
                    submitPerformSong.value as PerformSongCreate
                )
            ).data
        } else {
            submitted.value = (
                await updatePerformSong(
                    props.performSong.id,
                    submitPerformSong.value
                )
            ).data
        }
    } catch (e) {
        const msg = spotifyIdErrorMessage(e)
        if (msg === undefined) throw e
        spotifyError.value = msg
        return
    }
    snackbar.value = true
    app.loadPerformSongs()
    // a song headed for the learning queue needs a sheet next
    const toSheets = !props.performSong && !submitted.value.learned
    router.push({
        name: 'performSong',
        params: { id: submitted.value.id },
        hash: toSheets ? '#arrangements' : undefined,
    })
}
// the 422 from a save carries FastAPI's validation-error shape
function spotifyIdErrorMessage(e: unknown): string | undefined {
    if (!isAxiosError(e) || e.response?.status !== 422) return
    const detail = e.response.data?.detail
    if (!Array.isArray(detail)) return
    const err = detail.find(
        (d: { loc?: string[] }) => d.loc?.at(-1) === 'spotify_id'
    )
    return err?.msg
}

const spotifyLoading = ref(false)
const spotifyError = ref('')
const spotifyNote = ref('')
const usedById = ref<number | null>(null)
const usedBy = computed(() => {
    if (usedById.value === null) return
    const song = app.performSongs?.find((s) => s.id === usedById.value)
    return { id: usedById.value, name: song ? `“${song.name}”` : 'another song' }
})
// the value the last lookup was for, so blur after a paste doesn't repeat it
let lookedUp = ''
let lookupSeq = 0

// also abandons a lookup in flight, so its answer can't land on a changed field
function clearSpotifyStatus() {
    lookupSeq++
    spotifyLoading.value = false
    spotifyError.value = ''
    spotifyNote.value = ''
    usedById.value = null
}

// an error or warning is about the value it was found for; typing drops it
watch(
    () => submitPerformSong.value.spotify_id,
    (id) => {
        if ((id ?? '').trim() !== lookedUp) clearSpotifyStatus()
        // a picked result stays shown only while it's the song's recording
        if (picked.value && (id ?? '').trim() !== picked.value.spotify_id) {
            picked.value = null
        }
    }
)

// a pasted ID replaces the whole field: a partial Spotify ID is never wanted
function onSpotifyPaste(e: ClipboardEvent) {
    const text = e.clipboardData?.getData('text')
    if (!text) return
    e.preventDefault()
    submitPerformSong.value.spotify_id = text.trim()
    lookupSpotify(submitPerformSong.value.spotify_id)
}

// the song already using this recording, not counting the one being edited
function usedByOther(track: TrackSummaryRead): number | null {
    const owner = track.used_by_perform_song_id ?? null
    return owner !== props.performSong?.id ? owner : null
}

// shared by a looked-up ID and a picked search result
function applyTrack(track: TrackSummaryRead) {
    clearSpotifyStatus()
    lookedUp = track.spotify_id
    submitPerformSong.value.spotify_id = track.spotify_id
    // never overwrite what's been typed
    if (!submitPerformSong.value.name) {
        submitPerformSong.value.name = track.name
    }
    if (!submitPerformSong.value.artist_name) {
        submitPerformSong.value.artist_name = track.artist_name
    }
    usedById.value = usedByOther(track)
    // the warning names the song from the store's list, which a form opened
    // directly hasn't loaded yet, or which predates that song
    const owner = usedById.value
    if (owner !== null && !app.performSongs?.some((s) => s.id === owner)) {
        app.loadPerformSongs()
    }
}

const picked = ref<TrackSummaryRead | null>(null)
const searchText = ref('')
const searchResults = ref<TrackSummaryRead[]>([])
const searching = ref(false)
const searchError = ref('')
let searchTimer: ReturnType<typeof setTimeout> | undefined
let searchSeq = 0

function trackSubtitle(track: TrackSummaryRead) {
    const album = [track.album_name, track.release_year]
        .filter((x) => x)
        .join(' · ')
    return album ? `${track.artist_name} — ${album}` : track.artist_name
}

watch(searchText, (text) => {
    clearTimeout(searchTimer)
    const seq = ++searchSeq
    searching.value = false
    searchError.value = ''
    const q = (text ?? '').trim()
    if (q.length < 2) {
        searchResults.value = []
        return
    }
    // picking a result puts its title in the box; that's not a new search
    if (q === picked.value?.name) return
    searching.value = true
    searchTimer = setTimeout(async () => {
        try {
            const results = (await searchSpotifyTracks({ q })).data
            if (seq === searchSeq) searchResults.value = results
        } catch {
            if (seq === searchSeq) searchError.value = "Couldn't reach Spotify"
        } finally {
            if (seq === searchSeq) searching.value = false
        }
    }, 300)
})

function onPick(track: TrackSummaryRead | null) {
    if (track) applyTrack(track)
}

function resetSearch() {
    clearTimeout(searchTimer)
    searchSeq++
    picked.value = null
    searchText.value = ''
    searchResults.value = []
    searchError.value = ''
    searching.value = false
}

async function lookupSpotify(raw: string | null | undefined) {
    const id = (raw ?? '').trim()
    if (id === lookedUp) return
    lookedUp = id
    clearSpotifyStatus()
    if (!id) return
    const seq = ++lookupSeq
    spotifyLoading.value = true
    try {
        const track = (await lookupSpotifyTrack({ id })).data
        if (seq !== lookupSeq) return
        applyTrack(track)
    } catch (e) {
        if (seq !== lookupSeq) return
        if (isAxiosError(e) && e.response?.status === 404) {
            spotifyError.value = 'Spotify has no track with this ID'
        } else {
            spotifyNote.value = "Couldn't reach Spotify to check this ID. You can still save."
        }
    } finally {
        if (seq === lookupSeq) spotifyLoading.value = false
    }
}

async function onDelete() {
    if (!props.performSong) throw Error
    deletePerformSong(props.performSong.id)
}
watchEffect(() => {
    if (props.performSong) {
        submitPerformSong.value.name = props.performSong.name
        submitPerformSong.value.artist_name = props.performSong.artist_name
        submitPerformSong.value.learned = props.performSong.learned
        submitPerformSong.value.spotify_id = props.performSong.spotify_id
        // the form stays mounted when moving between songs
        lookedUp = props.performSong.spotify_id ?? ''
        clearSpotifyStatus()
        resetSearch()
        submitPerformSong.value.notes = props.performSong.notes
        submitPerformSong.value.perform_url = props.performSong.perform_url
        submitPerformSong.value.created_at = dateFmt(
            props.performSong.created_at
        )
        submitPerformSong.value.key = props.performSong.key
        submitPerformSong.value.capo = props.performSong.capo
        submitPerformSong.value.lyrics = props.performSong.lyrics
        submitPerformSong.value.learned_dt = dateFmt(
            props.performSong.learned_dt
        )
    }
})
</script>
