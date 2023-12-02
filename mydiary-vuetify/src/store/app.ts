// Utilities
import { defineStore } from 'pinia'
import { computed, nextTick, ref, watchEffect } from 'vue'
import Axios from 'axios'
import { readPerformSongsList, PerformSongRead, spotifyHistoryCount } from '@/api'

// export const useAppStore = defineStore('app', {
//   state: () => ({
//     //
//   }),
// })

export const useAppStore = defineStore('app', () => {
  Axios.defaults.baseURL = '/api'

  const performSongs = ref<PerformSongRead[]>()
  async function loadPerformSongs() {
    performSongs.value = await readPerformSongsList({ limit: 5000 })
      .then((res) => {
        return res.data.sort((a, b) => a.name.localeCompare(b.name))
      })
  }
  function getPerformSongById(id: number) {
    if (!performSongs.value) return
    return performSongs.value.filter((performSong) => performSong.id === id)[0]
  }

  return { performSongs, loadPerformSongs, getPerformSongById }
})
