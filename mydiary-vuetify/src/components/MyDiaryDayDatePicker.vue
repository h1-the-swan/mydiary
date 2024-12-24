<template>
    <DatePicker
        ref="calendar"
        :model-value="getDate"
        @update:model-value="updateDate"
        :attributes="attributes"
        expanded
    />
    <v-btn @click="calendarLoadJoplinInfo">
        refresh diary details for calendar
    </v-btn>
</template>

<script setup lang="ts">
import { computed, ref, watch, watchEffect } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from '@/store/app'
import { getDate } from '@/util'
import { DatePicker } from 'v-calendar'
import 'v-calendar/style.css'
import { AttributeConfig } from 'v-calendar/dist/types/src/utils/attribute'
const router = useRouter()
const route = useRoute()
const app = useAppStore()
const joplinInfoAllDays = ref<any[]>([])
const calendar = ref<any>(null)
const calendarVisibleDates = computed<Date[]>(() => {
    if (calendar.value == null) {
        return []
    }
    return calendar.value.calendarRef.days.map((d: any) => d.date)
})
async function calendarLoadJoplinInfo() {
    if (!calendarVisibleDates.value.length) return
    const sortedDates = calendarVisibleDates.value.sort(
        (a: any, b: any) => a - b
    )
    const minDt = sortedDates[0].toISOString().split('T')[0]
    const maxDt = sortedDates[sortedDates.length - 1]
        .toISOString()
        .split('T')[0]
    app.loadJoplinInfoAllDays(minDt, maxDt)
}
const attributes = computed<AttributeConfig[]>(() => [
    {
        highlight: {
            fillMode: 'outline',
            style: { 'border-width': '1px', 'border-style': 'dashed' },
        },
        dates: joplinInfoAllDays.value.map(
            (item: any) => new Date(`${item.title}T00:00`)
        ),
    },
    {
        dot: 'blue',
        dates: joplinInfoAllDays.value
            .filter((item: any) => item.has_words)
            .map((item: any) => new Date(`${item.title}T00:00`)),
    },
    {
        dot: 'orange',
        dates: joplinInfoAllDays.value
            .filter((item: any) => item.has_images)
            .map((item: any) => new Date(`${item.title}T00:00`)),
    },
])
function updateDate(val: any) {
    const newQD = val.toISOString().split('T')[0]
    router.push({ query: { dt: newQD } })
}
watchEffect(() => (joplinInfoAllDays.value = app.joplinInfoAllDays))
</script>
