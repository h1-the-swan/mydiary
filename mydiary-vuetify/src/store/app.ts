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

    const timeZoneChanges = ref<TimeZoneChange[]>()
    async function loadTimeZoneChanges() {
        timeZoneChanges.value = await readTimeZoneChangeList({
            limit: 5000,
        }).then((res) => {
            return res.data
        })
    }

    return {
        performSongs,
        loadPerformSongs,
        getPerformSongById,
        joplinInfoAllDays,
        loadJoplinInfoAllDays,
        timeZoneChanges,
        loadTimeZoneChanges,
    }
})
