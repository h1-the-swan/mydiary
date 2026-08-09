/**
 * Word helpers for the Spelling Bee tracker, mirroring the backend's
 * spelling_bee.py so the entry form can validate a paste as it is typed
 * rather than waiting for a round trip.
 */

// the Bee never accepts words shorter than this
export const MIN_WORD_LEN = 4
// a hive is always seven letters: one centre, six outer
export const HIVE_SIZE = 7

export function normalizeWord(word: string): string {
    return (word || '').trim().toUpperCase().replace(/[^A-Z]/g, '')
}

/**
 * Split a pasted answer list into words, keeping the order they were typed.
 * The NYT list copies one word per line, but people also use spaces or commas.
 */
export function parseWords(blob: string): string[] {
    const seen = new Set<string>()
    const out: string[] = []
    for (const chunk of (blob || '').split(/[\s,;]+/)) {
        const word = normalizeWord(chunk)
        if (word && !seen.has(word)) {
            seen.add(word)
            out.push(word)
        }
    }
    return out
}

/**
 * A puzzle only has seven letters, so any valid word using seven distinct
 * ones is necessarily a pangram. Nothing to record -- just count.
 */
export function isPangram(word: string): boolean {
    return new Set(normalizeWord(word)).size === HIVE_SIZE
}

export function distinctLetters(words: string[]): Set<string> {
    return new Set(words.join('').split(''))
}

/**
 * A date as YYYY-MM-DD in the *local* calendar.
 *
 * Deliberately not toISOString(): the date picker hands back local midnight,
 * which converts to the previous day in UTC anywhere east of Greenwich.
 */
export function isoDate(d: Date): string {
    return d.toLocaleDateString('en-CA')
}

export function formatDate(value: string | Date | null | undefined): string {
    if (!value) return ''
    const d = typeof value === 'string' ? new Date(`${value}T00:00`) : value
    return d.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
    })
}

/** Yesterday -- you enter a puzzle's answers the day after playing it. */
export function yesterday(): Date {
    const d = new Date()
    d.setDate(d.getDate() - 1)
    return d
}
