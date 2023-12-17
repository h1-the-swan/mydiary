<template>
<v-data-table></v-data-table>
</template>

<script lang="ts" setup>
import { ref } from 'vue';

const headers = ref([
  { title: 'id', key: 'id' },
  { title: 'name', key: 'name' },
  { title: 'artist_name', key: 'artist_name' },
  { title: 'learned', key: 'learned' },
])
</script>