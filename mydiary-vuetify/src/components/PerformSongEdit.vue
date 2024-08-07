<template>
    <v-card>
        <v-form>
            <v-card-title>
                <span class="text-h5">{{ formTitle }}</span>
            </v-card-title>

            <v-card-text>
                <v-container>
                    <v-row>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.name"
                                label="Name"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.artist_name"
                                label="Artist Name"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-checkbox
                                v-model="submitPerformSong.learned"
                                label="Learned"
                            ></v-checkbox>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.spotify_id"
                                label="Spotify ID"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.notes"
                                label="notes"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.perform_url"
                                label="perform_url"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.created_at"
                                label="created_at"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.key"
                                label="key"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.capo"
                                label="capo"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.lyrics"
                                label="lyrics"
                            ></v-text-field>
                        </v-col>
                        <v-col cols="12" sm="6" md="4">
                            <v-text-field
                                v-model="submitPerformSong.learned_dt"
                                label="learned_dt"
                            ></v-text-field>
                        </v-col>
                    </v-row>
                </v-container>
            </v-card-text>
            <v-card-actions>
                <v-btn color="primary" variant="elevated" @click="onSave"
                    >Save</v-btn
                >
                <v-btn color="red" disabled variant="elevated" @click="onDelete"
                    >Delete</v-btn
                >
            </v-card-actions>
        </v-form>
        <v-snackbar v-if="submitted" v-model="snackbar">
            PerformSong saved. ID: {{ submitted.id }}
            <template v-slot:actions>
                <v-btn color="green" variant="text" @click="snackbar = false">
                    Close
                </v-btn>
            </template>
        </v-snackbar>
    </v-card>
</template>

<script lang="ts" setup>
import { computed } from 'vue'
import { watchEffect } from 'vue'
import { PerformSongUpdate } from '@/api'
import { ref } from 'vue'
import { useDate } from 'vuetify'
import {
    PerformSongRead,
    updatePerformSong,
    createPerformSong,
    PerformSongCreate,
    deletePerformSong,
} from '@/api'
import { useAppStore } from '@/store/app'
import { useRouter } from 'vue-router'
const date = useDate()
const props = defineProps<{
    performSong?: PerformSongRead
}>()
const router = useRouter()
const app = useAppStore()
const submitPerformSong = ref<PerformSongUpdate>({})
const submitted = ref<PerformSongRead>()
const snackbar = ref(false)
const formTitle = computed(() => {
    if (props.performSong) {
        return `Edit PerformSong (ID: ${props.performSong.id})`
    } else {
        return 'Submit a new PerformSong'
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
    if (
        submitPerformSong.value.spotify_id &&
        submitPerformSong.value.spotify_id.startsWith('http')
    ) {
        const spotifyIdURL = new URL(submitPerformSong.value.spotify_id)
        const cleanedId = spotifyIdURL.pathname.split('/').at(-1)
        submitPerformSong.value.spotify_id = cleanedId
    }
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
    snackbar.value = true
    console.log(submitted.value)
    app.loadPerformSongs()
    router.push({ name: 'performSong', params: { id: submitted.value.id } })
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
watchEffect(() => console.log(submitPerformSong.value))
</script>
