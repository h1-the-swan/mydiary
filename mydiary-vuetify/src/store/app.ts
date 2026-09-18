// Utilities
import { defineStore } from 'pinia'
import { computed, nextTick, ref, watchEffect } from 'vue'
import Axios from 'axios'
import {
    readPerformSongsList,
    PerformSongRead,
    spotifyHistoryCount,
    joplinGetInfoAllDays,
    TimeZoneChange,
    readTimeZoneChangeList,
    SpellingBeeWordRead,
    SpellingBeeHiveRead,
    readSpellingBeeWordsList,
    readSpellingBeeHivesList,
    TagRead,
    TagNamespaceRead,
    readTags,
    readTagNamespaces,
} from '@/api'

// export const useAppStore = defineStore('app', {
//   state: () => ({
//     //
//   }),
// })

export const useAppStore = defineStore('app', () => {
    Axios.defaults.baseURL = '/api'

    const performSongs = ref<PerformSongRead[]>()
    async function loadPerformSongs() {
        performSongs.value = await readPerformSongsList({ limit: 5000 }).then(
            (res) => {
                return res.data.sort((a, b) => a.name.localeCompare(b.name))
            }
        )
    }
    function getPerformSongById(id: number) {
        if (!performSongs.value) return
        return performSongs.value.filter(
            (performSong) => performSong.id === id
        )[0]
    }

    const joplinInfoAllDays = ref<any[]>([])
    async function loadJoplinInfoAllDays(min_dt: string, max_dt: string) {
        joplinInfoAllDays.value = (
            await joplinGetInfoAllDays({ min_dt: min_dt, max_dt: max_dt })
        ).data
    }
    const calendarShouldUpdate = ref<boolean>(false)

    const timeZoneChanges = ref<TimeZoneChange[]>()
    async function loadTimeZoneChanges() {
        timeZoneChanges.value = await readTimeZoneChangeList({
            limit: 5000,
        }).then((res) => {
            return res.data
        })
    }

    // the backend already sorts these most-missed first
    const spellingBeeWords = ref<SpellingBeeWordRead[]>()
    async function loadSpellingBeeWords() {
        spellingBeeWords.value = await readSpellingBeeWordsList({
            limit: 5000,
        }).then((res) => {
            return res.data
        })
    }

    const spellingBeeHives = ref<SpellingBeeHiveRead[]>()
    async function loadSpellingBeeHives() {
        spellingBeeHives.value = await readSpellingBeeHivesList({
            limit: 5000,
        }).then((res) => {
            return res.data
        })
    }

    // every tag, as the backend orders them (bare tags first, then by
    // namespace and slug); the chips' suggestion list and the tags index
    const tags = ref<TagRead[]>()
    async function loadTags() {
        tags.value = await readTags({ limit: 5000 }).then((res) => res.data)
    }
    const tagNamespaces = ref<TagNamespaceRead[]>()
    async function loadTagNamespaces() {
        tagNamespaces.value = await readTagNamespaces().then((res) => res.data)
    }

    return {
        performSongs,
        loadPerformSongs,
        getPerformSongById,
        joplinInfoAllDays,
        loadJoplinInfoAllDays,
        calendarShouldUpdate,
        timeZoneChanges,
        loadTimeZoneChanges,
        spellingBeeWords,
        loadSpellingBeeWords,
        spellingBeeHives,
        loadSpellingBeeHives,
        tags,
        loadTags,
        tagNamespaces,
        loadTagNamespaces,
    }
})
