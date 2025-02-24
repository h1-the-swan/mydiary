<template>
    <v-container id="performsong-main">
        <v-list>
            <v-list-item>
                <PerformSongsDropdown
                    v-if="performSongsList"
                    :items="performSongsList"
                />
            </v-list-item>
            <v-list-item>
                <PerformSongsRandomButton
                    v-if="performSongsList"
                    :items="performSongsList"
                    :current-id="Number(props.id)"
                />
            </v-list-item>
        </v-list>
        <PerformSongCard :perform-song="performSong" :image-url="imageUrl" />
        <PerformSongEdit :perform-song="performSong" />
        <v-card title="performSongs" flat>
            <template v-slot:text>
                <v-text-field
                    v-model="search"
                    label="Search"
                    prepend-inner-icon="mdi-magnify"
                    variant="outlined"
                    hide-details
                    single-line
                ></v-text-field>
            </template>

            <v-data-table
                v-if="performSongsList"
                :items="performSongsList"
                :headers="displayCols"
                items-per-page="100"
                :search="search"
            >
                <template v-slot:item="{ item }">
                    <tr>
                        <td>{{ item.id }}</td>
                        <td>
                            <router-link
                                :to="{
                                    name: 'performSong',
                                    params: { id: item.id },
                                    hash: '#performsong-main',
                                }"
                            >
                                {{ item.name }}
                            </router-link>
                        </td>
                        <td>{{ item.artist_name }}</td>
                        <td>{{ item.created_at }}</td>
                        <td>{{ item.learned }}</td>
                        <td>{{ item.learned_dt }}</td>
                    </tr>
                </template>
            </v-data-table>
        </v-card>
    </v-container>
</template>

<script lang="ts" setup>
import PerformSongCard from '@/components/PerformSongCard.vue'
import PerformSongsDropdown from '@/components/PerformSongsDropdown.vue'
import PerformSongsRandomButton from '@/components/PerformSongsRandomButton.vue'
import PerformSongEdit from '@/components/PerformSongEdit.vue'
import { computed, nextTick, ref, watch, watchEffect } from 'vue'
import Axios from 'axios'
Axios.defaults.baseURL = '/api'
import {
    readPerformSong,
    PerformSongRead,
    getSpotifyImageUrl,
    readPerformSongsList,
} from '@/api'
import { onMounted } from 'vue'
import { useAppStore } from '@/store/app'
const app = useAppStore()
const props = defineProps<{
    id: number | string | undefined
}>()
const performSong = ref<PerformSongRead>()
const imageUrl = ref('')
const performSongsList = ref<PerformSongRead[]>()
const displayCols = ref(
    ['id', 'name', 'artist_name', 'created_at', 'learned', 'learned_dt'].map(
        (x) => {
            return { key: x, title: x }
        }
    )
)
const search = ref<string>('')
onMounted(async () => {
    await app.loadPerformSongs()
    performSongsList.value = app.performSongs
})
watchEffect(async () => {
    imageUrl.value = ''
    // performSong.value = await readPerformSong(Number(props.id)).then((res) => res.data);
    performSong.value = app.getPerformSongById(Number(props.id))
})
watchEffect(async () => {
    if (performSong.value && performSong.value.spotify_id) {
        imageUrl.value = await getSpotifyImageUrl(
            performSong.value.spotify_id
        ).then((res) => res.data)
    }
})
</script>
