<template>
    <page-shell id="performsong-main" :title="performSong ? 'Song' : 'Songs'">
        <template #actions>
            <PerformSongsDropdown
                v-if="performSongsList"
                :items="performSongsList"
            />
            <PerformSongsRandomButton
                v-if="performSongsList"
                :items="performSongsList"
                :current-id="Number(props.id)"
            />
        </template>

        <template v-if="performSong">
            <PerformSongCard
                class="mb-8"
                :perform-song="performSong"
                :image-url="imageUrl"
            />
            <PerformSongEdit class="mb-8" :perform-song="performSong" />
        </template>

        <section>
            <section-header label="All songs" :meta="songCountLabel">
                <template #actions>
                    <v-btn
                        v-if="performSong"
                        size="small"
                        variant="text"
                        :append-icon="
                            showList ? 'mdi-chevron-up' : 'mdi-chevron-down'
                        "
                        @click="showList = !showList"
                    >
                        {{ showList ? 'Hide' : 'Show' }}
                    </v-btn>
                </template>
            </section-header>

            <v-expand-transition>
                <div v-show="showList">
                    <v-text-field
                        v-model="search"
                        class="mb-4"
                        label="Search songs"
                        prepend-inner-icon="mdi-magnify"
                        hide-details
                        single-line
                        clearable
                    ></v-text-field>

                    <v-data-table
                        v-if="performSongsList"
                        :items="performSongsList"
                        :headers="displayCols"
                        :items-per-page="25"
                        :search="search"
                    >
                        <template v-slot:item="{ item }">
                            <tr>
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
                                <td>{{ dateFmt(item.created_at) }}</td>
                                <td>
                                    <v-icon
                                        v-if="item.learned"
                                        icon="mdi-check"
                                        color="success"
                                        size="small"
                                        aria-label="Learned"
                                    />
                                    <span v-else class="text-disabled">—</span>
                                </td>
                                <td>{{ dateFmt(item.learned_dt) }}</td>
                            </tr>
                        </template>
                    </v-data-table>
                </div>
            </v-expand-transition>
        </section>
    </page-shell>
</template>

<script lang="ts" setup>
import PageShell from '@/components/PageShell.vue'
import SectionHeader from '@/components/SectionHeader.vue'
import PerformSongCard from '@/components/PerformSongCard.vue'
import PerformSongsDropdown from '@/components/PerformSongsDropdown.vue'
import PerformSongsRandomButton from '@/components/PerformSongsRandomButton.vue'
import PerformSongEdit from '@/components/PerformSongEdit.vue'
import { computed, ref, watchEffect } from 'vue'
import Axios from 'axios'
Axios.defaults.baseURL = '/api'
import { PerformSongRead, getSpotifyImageUrl } from '@/api'
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
    [
        { key: 'name', title: 'Song' },
        { key: 'artist_name', title: 'Artist' },
        { key: 'created_at', title: 'Added' },
        { key: 'learned', title: 'Learned' },
        { key: 'learned_dt', title: 'Learned on' },
    ]
)
const search = ref<string>('')
// on a single-song route the full list is secondary, so it starts collapsed
const showList = ref(!props.id)
const songCountLabel = computed<string>(() =>
    performSongsList.value ? `${performSongsList.value.length}` : ''
)
function dateFmt(dateStr: string | null | undefined) {
    if (!dateStr) return ''
    return new Date(dateStr).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
    })
}
onMounted(async () => {
    await app.loadPerformSongs()
    performSongsList.value = app.performSongs
})
watchEffect(async () => {
    imageUrl.value = ''
    performSong.value = app.getPerformSongById(Number(props.id))
})
watchEffect(async () => {
    if (performSong.value && performSong.value.spotify_id) {
        imageUrl.value = await getSpotifyImageUrl(
            performSong.value.spotify_id
        ).then((res) => res.data)
        imageUrl.value = imageUrl.value.replace(/"/g, '')
    }
})
</script>
