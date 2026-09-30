import { afterEach, describe, expect, it } from 'vitest'
import { fromDateStr, toDateStr } from './util'

const originalTZ = process.env.TZ

afterEach(() => {
    // Assigning undefined would store the string "undefined", which Node reads as UTC
    if (originalTZ === undefined) delete process.env.TZ
    else process.env.TZ = originalTZ
})

// Node rereads TZ on each change, so every case below runs in its zone.
// The offset check guards against the zone silently not applying.
const zones = [
    { tz: 'America/Los_Angeles', januaryOffset: 480 },
    { tz: 'Pacific/Auckland', januaryOffset: -780 },
]

describe.each(zones)('calendar date helpers in $tz', ({ tz, januaryOffset }) => {
    const useZone = () => {
        process.env.TZ = tz
        expect(new Date(2026, 0, 15).getTimezoneOffset()).toBe(januaryOffset)
    }

    it('reads a date string as local midnight on that day', () => {
        useZone()
        const d = fromDateStr('2026-05-01')
        expect(d.getFullYear()).toBe(2026)
        expect(d.getMonth()).toBe(4)
        expect(d.getDate()).toBe(1)
        expect(d.getHours()).toBe(0)
    })

    it('round-trips a date string', () => {
        useZone()
        for (const s of ['2026-01-01', '2026-05-01', '2026-12-31', '2024-02-29']) {
            expect(toDateStr(fromDateStr(s))).toBe(s)
        }
    })

    it('formats a late-evening local time as that local day', () => {
        useZone()
        expect(toDateStr(new Date(2026, 4, 1, 23, 30))).toBe('2026-05-01')
    })
})

describe('calendar date helpers where midnight is skipped', () => {
    it('keeps the day when DST starts at midnight', () => {
        // In Chile, local midnight on 2026-09-06 doesn't exist: clocks go from 00:00 to 01:00.
        process.env.TZ = 'America/Santiago'
        const d = fromDateStr('2026-09-06')
        expect(d.getHours()).toBe(1) // midnight really was skipped
        expect(d.getDate()).toBe(6)
        expect(toDateStr(d)).toBe('2026-09-06')
    })
})
