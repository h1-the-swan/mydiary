<template>
    <v-chip v-if="credentialsValid == undefined">
        Google Calendar credentials validation loading...
    </v-chip>
    <v-chip
        v-else-if="credentialsValid == true"
        color="green"
        variant="flat"
        @click="setCredentialsValidOrNo"
    >
        <v-icon icon="mdi-check-circle" start />
        Google Calendar credentials
    </v-chip>
    <v-chip v-else color="red" variant="flat" @click="invalidClick">
        <v-icon icon="mdi-alert-circle" start />
        Invalid Google Credentials. Click to refresh.
    </v-chip>
    <v-dialog v-model="dialog" max-width="600">
        <v-card title="Refresh Google Calendar credentials">
            <v-form
                @submit.prevent="() => submitGCalRefreshToken(authCodeGCal)"
            >
                <v-card-text>
                    Click on
                    <a :href="authUrl" target="_blank" rel="noreferrer">
                        this link
                    </a>
                    , follow the instructions, and paste the code given into the
                    field below:
                </v-card-text>
                <v-text-field
                    v-model="authCodeGCal"
                    color="primary"
                    label="Code"
                ></v-text-field>
                <v-card-actions>
                    <v-btn type="submit" text="Submit"></v-btn>
                </v-card-actions>
            </v-form>
        </v-card>
    </v-dialog>
    <v-snackbar v-model="snackbar" timeout="3000">
        GCal auth token was refreshed

        <template v-slot:actions>
            <v-btn color="green" variant="text" @click="snackbar = false">
                Close
            </v-btn>
        </template>
    </v-snackbar>
</template>

<script lang="ts" setup>
import Axios from 'axios'
Axios.defaults.baseURL = '/api'
import { checkGCalAuth, getGCalAuthUrl, refreshGCalToken } from '@/api'
import { ref, onMounted, computed } from 'vue'
const loading = ref(false)
const dialog = ref(false)
const credentialsValid = ref<boolean>()
const authUrl = ref('')
const authCodeGCal = ref('')
const snackbar = ref(false)
async function setCredentialsValidOrNo() {
    await checkGCalAuth()
        .then(() => (credentialsValid.value = true))
        .catch(() => (credentialsValid.value = false))
}
async function submitGCalRefreshToken(code: string) {
    snackbar.value = false
    await refreshGCalToken({ code: code })
    dialog.value = false
    snackbar.value = true
}
async function invalidClick() {
    await setCredentialsValidOrNo()
    if (credentialsValid.value == false) {
        dialog.value = true
    }
}
onMounted(async () => {
    setCredentialsValidOrNo()
    authUrl.value = (await getGCalAuthUrl()).data
})
</script>
