<template>
  <h1>Home</h1>
  <v-btn @click="getDBStatus">get db status</v-btn>
</template>

<script lang="ts" setup>
import axios from 'axios'
axios.defaults.baseURL = '/api'
async function getDBStatus() {
  const x = (await axios.get('/db_status')).data
  console.log(x)
  return x.sqlite_file_exists
}
</script>
