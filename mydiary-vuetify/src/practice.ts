/** Small helpers shared by the practice views. */
import type { Instrument } from './chords'
import { LEVELS, type Level } from './chordpro'

export const LEVEL_LABELS: Record<Level, string> = {
    full: 'Reading',
    letters: 'First letters',
    cues: 'First words',
    memorized: 'Memorized',
}

export function levelColor(level: Level): string {
    return `level-${level}`
}

export function levelMap(rows: { section_key: string; level: string }[] | undefined): Record<string, Level> {
    const out: Record<string, Level> = {}
    for (const row of rows ?? []) {
        if ((LEVELS as readonly string[]).includes(row.level)) out[row.section_key] = row.level as Level
    }
    return out
}

/** The backend returns UTC datetimes without a zone; read them as UTC. */
export function utcDate(s?: string | null): Date | null {
    if (!s) return null
    return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(s) ? s : `${s}Z`)
}

export function shortDate(s?: string | null): string {
    const d = utcDate(s)
    return d ? d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : ''
}

export const INSTRUMENTS: Instrument[] = ['guitar', 'ukulele']
export const INSTRUMENT_LABELS: Record<string, string> = { guitar: 'Guitar', ukulele: 'Ukulele' }

/**
 * A capo field's value as the API wants it. A cleared number field gives '',
 * which `v-model.number` leaves as a string, so anything that isn't a whole
 * number reads as no capo.
 */
export function capoOrNull(v: unknown): number | null {
    if (v === '' || v === null || v === undefined) return null
    const n = Number(v)
    return Number.isInteger(n) ? n : null
}
