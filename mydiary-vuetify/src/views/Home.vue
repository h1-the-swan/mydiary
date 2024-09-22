<template>
  <h1>Home</h1>
  <v-btn @click="getDBStatus">get db status</v-btn>
</template>

<script lang="ts" setup>
import axios from 'axios'
import { dbStatus } from '@/api'
axios.defaults.baseURL = '/api'
async function getDBStatus() {
  const x = (await dbStatus({more: true})).data
  // const x = (await axios.get('/db_status')).data
  console.log(x)
  return x.db_is_initialized
}
</script>
