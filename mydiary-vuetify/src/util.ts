import { computed, ref, watch, watchEffect } from 'vue'
import { useRouter, useRoute } from 'vue-router'

export function useDiaryDate() {
    const route = useRoute()
    return computed(() => {
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
}

export function toDateStr(dt: Date): string {
    const year = dt.getFullYear()
    const month = String(dt.getMonth() + 1).padStart(2, '0')
    const day = String(dt.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
}

// Inverse of toDateStr: 'YYYY-MM-DD' to local midnight. new Date('YYYY-MM-DD')
// parses as UTC midnight, which is the previous day west of UTC.
export function fromDateStr(s: string): Date {
    const [year, month, day] = s.split('-').map(Number)
    return new Date(year, month - 1, day)
}
