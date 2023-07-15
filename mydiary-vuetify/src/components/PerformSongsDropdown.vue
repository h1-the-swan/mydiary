<template>
	<v-btn>
		Choose a song
		<v-menu activator="parent">
			<v-list>
				<v-list-item v-for="(item, index) in props.items" :key="index" :value="item.id"
					@click="$router.push(`/performSongs/${item.id}`)">
					<v-list-item-title>{{ item.name }}</v-list-item-title>
				</v-list-item>
			</v-list>
		</v-menu>
	</v-btn>
</template>

<script lang="ts" setup>
import { PerformSongRead } from '@/api';

const props = defineProps<{
	items: PerformSongRead[];
}>();
</script>