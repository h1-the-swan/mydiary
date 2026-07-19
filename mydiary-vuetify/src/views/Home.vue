<template>
  <v-container>
    <h1 class="text-h3 font-weight-bold mb-6">mydiary</h1>

    <v-row>
      <v-col
        v-for="link in links"
        :key="link.name"
        cols="12"
        sm="6"
        md="4"
      >
        <v-card
          :to="{ name: link.name }"
          class="fill-height"
          hover
        >
          <v-card-item>
            <template #prepend>
              <v-icon :icon="link.icon" size="large" />
            </template>
            <v-card-title>{{ link.title }}</v-card-title>
            <v-card-subtitle>{{ link.subtitle }}</v-card-subtitle>
          </v-card-item>
        </v-card>
      </v-col>
    </v-row>

    <div class="mt-8">
      <v-btn @click="getDBStatus">get db status</v-btn>
    </div>
  </v-container>
</template>

<script lang="ts" setup>
import axios from 'axios'
import { dbStatus } from '@/api'
axios.defaults.baseURL = '/api'

const links = [
  {
    name: 'MyDiaryDay',
    title: 'Diary Day',
    subtitle: 'View and edit a day’s journal entry',
    icon: 'mdi-notebook',
  },
  {
    name: 'performSongs',
    title: 'Perform Songs',
    subtitle: 'Browse the guitar songs tracker',
    icon: 'mdi-guitar-acoustic',
  },
  {
    name: 'new performSong',
    title: 'New Perform Song',
    subtitle: 'Add a song to the tracker',
    icon: 'mdi-plus-circle',
  },
  {
    name: 'timeZoneChange',
    title: 'Time Zone Change',
    subtitle: 'Record a time zone change',
    icon: 'mdi-earth',
  },
]

async function getDBStatus() {
  const x = (await dbStatus({ more: true })).data
  console.log(x)
  return x.db_is_initialized
}
</script>
