<template>
  <v-btn @click="onClick" :loading="loading">
    Check GCal Auth
  </v-btn>
  <v-alert v-if="credentialsValid !== undefined" :type="credentialsValid ? 'success' : 'error'" :text="alertText"
    closable></v-alert>
  <p>
    <a :href="authUrl" target="_blank" rel="noreferrer">
      {{ authUrl }}
    </a>
  </p>
  <v-card width="550">
    <v-form @submit.prevent="() => submitGCalRefreshToken(authCodeGCal)">
      <v-text-field v-model="authCodeGCal" color="primary"></v-text-field>
      <v-btn type="submit" text="Submit"></v-btn>
      <v-snackbar v-model="snackbar" timeout="3000">
        GCal auth token was refreshed

        <template v-slot:actions>
          <v-btn color="green" variant="text" @click="snackbar = false">
            Close
          </v-btn>
        </template>
      </v-snackbar>
    </v-form>
  </v-card>
</template>

<script lang="ts" setup>
import Axios from 'axios';
Axios.defaults.baseURL = '/api';
import { checkGCalAuth, getGCalAuthUrl, refreshGCalToken } from '@/api';
import { ref } from 'vue';
import { onMounted } from 'vue';
import { computed } from 'vue';
const loading = ref(false);
const credentialsValid = ref<boolean>()
const authUrl = ref('')
const authCodeGCal = ref('')
const snackbar = ref(false)
const alertText = computed(() => {
  if (credentialsValid.value) {
    return 'Auth credentials are working'
  } else {
    return 'Auth credentials not working. Please refresh'
  }
})
async function onClick() {
  loading.value = true
  await checkGCalAuth()
    .then(() => credentialsValid.value = true)
    .catch(() => credentialsValid.value = false)
  loading.value = false
}
async function submitGCalRefreshToken(code: string) {
  snackbar.value = false
  await refreshGCalToken({ code: code })
  snackbar.value = true
}
onMounted(async () => {
  authUrl.value = (await getGCalAuthUrl()).data
})
</script>