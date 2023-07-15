<template>
	<v-btn @click="$router.push(`/performSongs/${randomPerformSong()}`)">
		Random song
	</v-btn>

</template>

<script lang="ts" setup>
import { PerformSongRead } from '@/api';

const props = defineProps<{
	items: PerformSongRead[];
	currentId?: number;
}>();
function randomPerformSong() {
	const learnedSongs = props.items.filter((song) => song.learned === true)
		.filter((song) => song.id !== props.currentId);
	const randomSong = learnedSongs[Math.floor(Math.random() * learnedSongs.length)];
	return randomSong.id;
}
</script>