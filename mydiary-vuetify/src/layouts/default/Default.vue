<template>
  <v-app>
    <v-layout>
      <default-bar />

      <default-view />
    </v-layout>
  </v-app>
</template>

<script lang="ts" setup>
import DefaultBar from './AppBar.vue'
import DefaultView from './View.vue'
</script>
