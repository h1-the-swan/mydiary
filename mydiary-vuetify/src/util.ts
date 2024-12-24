import { computed, ref, watch, watchEffect } from 'vue'
import { useRouter, useRoute } from 'vue-router'

export const getDate = computed(() => {
    const route = useRoute()
    const qd = route.query.dt
    if (!qd || qd === 'yesterday') {
        const dt = new Date()
        dt.setDate(dt.getDate() - 1)
        return dt
    } else if (qd === 'today') {
        return new Date()
    } else {
        return new Date(`${route.query.dt as string}T00:00`)
    }
})

export function updateDate(val: any) {
    const router = useRouter()
    if (router == undefined) return
    const newQD = val.toISOString().split('T')[0]
    router.push({ query: { dt: newQD } })
}
