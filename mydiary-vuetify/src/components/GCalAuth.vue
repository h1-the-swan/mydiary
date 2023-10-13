<template>
  <v-btn @click="onClick" :loading="loading">
    Check GCal Auth
  </v-btn>
</template>

<script lang="ts" setup>
import Axios from 'axios';
Axios.defaults.baseURL = '/api';
import { checkGCalAuth } from '@/api';
import { ref } from 'vue';
const loading = ref(false);
async function onClick() {
  loading.value = true;
  await checkGCalAuth()
    .then((res) => console.log(res))
    .catch(() => console.log('auth credentials not working!'))
}
</script>