<template>
	<v-btn @click="onClick">
		Save recent Spotify tracks
	</v-btn>
</template>

<script lang="ts" setup>
import Axios from 'axios';
Axios.defaults.baseURL = '/api';
import { spotifySaveRecentTracksToDatabase } from '@/api';

async function onClick() {
	await spotifySaveRecentTracksToDatabase().then((res) => res.data).then((res) => console.log(res));
}
</script>