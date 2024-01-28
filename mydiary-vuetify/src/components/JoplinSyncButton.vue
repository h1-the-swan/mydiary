<template>
  <v-btn @click="onClick" :loading="loading">
    Joplin Sync
  </v-btn>
  <v-snackbar v-model="snackbar" timeout="3000">
    {{ snackbarMessage }}

    <template v-slot:actions>
      <v-btn color="green" variant="text" @click="snackbar = false">
        Close
      </v-btn>
    </template>
  </v-snackbar>
</template>

<script lang="ts" setup>
import Axios from 'axios'
Axios.defaults.baseURL = '/api'
import { joplinSync } from '@/api'
import { ref } from 'vue'

const loading = ref(false)
const snackbar = ref(false)
const snackbarMessage = ref('')

async function onClick() {
  loading.value = true
  await joplinSync()
    .then((res) => res.data)
    .then((res) => {
      snackbar.value = true
      snackbarMessage.value = res as string
      loading.value = false

    })
}
</script>