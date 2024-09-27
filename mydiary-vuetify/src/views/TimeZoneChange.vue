<template>
    <h1>Add time zone change</h1>
    <v-form @submit.prevent="onSubmit">
        <v-autocomplete
            label="Time zone before"
            v-model="tzBefore"
            :items="validTimeZones"
        ></v-autocomplete>
        <v-autocomplete
            label="Time zone after"
            v-model="tzAfter"
            :items="validTimeZones"
        ></v-autocomplete>
        <div class="w-75" style="width: auto">
            <h3>Choose Date/Time based on Time zone after</h3>
            <DatePicker
                ref="calendar"
                v-model="dt"
                timezone="UTC"
                mode="dateTime"
                expanded
            />
        </div>
        <v-btn type="submit" text="Submit"></v-btn>
    </v-form>
    <v-data-table
        v-if="timeZoneChangeList"
        :items="timeZoneChangeList"
        items-per-page="100"
    ></v-data-table>
</template>

<script setup lang="ts">
import Axios from 'axios'
Axios.defaults.baseURL = '/api'
import { useAppStore } from '@/store/app'
const app = useAppStore()
import { ref, onMounted } from 'vue'
import { DatePicker } from 'v-calendar'
import 'v-calendar/style.css'
import {
    createTimeZoneChange,
    readTimeZoneChangeList,
    TimeZoneChange,
} from '@/api'
const dt = ref(new Date())
const tzBefore = ref('')
const tzAfter = ref('')
const validTimeZones = ref<string[]>([])
const timeZoneChangeList = ref<TimeZoneChange[]>()
async function onSubmit() {
    console.log(dt.value.toISOString())
    console.log(tzBefore.value)
    console.log(tzAfter.value)
    await createTimeZoneChange({
        dt: dt.value.toISOString(),
        tz_before: tzBefore.value,
        tz_after: tzAfter.value,
    })
    await app.loadTimeZoneChanges()
    timeZoneChangeList.value = app.timeZoneChanges
}
onMounted(() => {
    validTimeZones.value = Intl.supportedValuesOf('timeZone')
})
onMounted(async () => {
    await app.loadTimeZoneChanges()
    timeZoneChangeList.value = app.timeZoneChanges
})
</script>
