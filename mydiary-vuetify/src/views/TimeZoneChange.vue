<template>
    <h1>Add time zone change</h1>
    <v-form @submit.prevent="onSubmit">
        <v-text-field
            label="Time zone before"
            v-model="tzBefore"
        ></v-text-field>
        <v-text-field label="Time zone after" v-model="tzAfter"></v-text-field>
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
</template>

<script setup lang="ts">
import Axios from 'axios';
Axios.defaults.baseURL = '/api';
import { ref } from 'vue'
import { DatePicker } from 'v-calendar'
import 'v-calendar/style.css'
import { createTimeZoneChange } from '@/api'
const dt = ref(new Date())
const tzBefore = ref('')
const tzAfter = ref('')
async function onSubmit() {
    console.log(dt.value.toISOString())
    console.log(tzBefore.value)
    console.log(tzAfter.value)
    await createTimeZoneChange({
        dt: dt.value.toISOString(),
        tz_before: tzBefore.value,
        tz_after: tzAfter.value,
    })
}
</script>
