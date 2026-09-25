/**
 * Chord fingerings for the sheets, from the chords-db library (MIT): guitar in
 * standard tuning and ukulele in GCEA. A sheet's own `{define}` beats the
 * library, which is how a fingering the user settled on gets remembered.
 *
 * The data is ~240 kB per instrument, so it is loaded on demand, not bundled
 * into the main chunk.
 */
import type { ChordDefine } from './chordpro'

export type Instrument = 'guitar' | 'ukulele'
export const STRINGS: Record<Instrument, number> = { guitar: 6, ukulele: 4 }

export interface Fingering {
    baseFret: number
    frets: number[] // relative to baseFret, 0 open, -1 muted, lowest string first
    fingers: number[]
    barres: number[] // relative frets that are barred
}

export interface ChordDb {
    chords: Record<string, { key: string; suffix: string; positions: Fingering[] }[]>
}

const cache: Partial<Record<Instrument, Promise<ChordDb>>> = {}

export function loadChordDb(instrument: Instrument): Promise<ChordDb> {
    cache[instrument] ??=
        instrument === 'guitar'
            ? import('@tombatossals/chords-db/lib/guitar.json').then((m) => (m.default ?? m) as unknown as ChordDb)
            : import('@tombatossals/chords-db/lib/ukulele.json').then((m) => (m.default ?? m) as unknown as ChordDb)
    return cache[instrument]!
}

const LETTER_PC: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 }

function pitchClass(note: string): number | null {
    const m = note.match(/^([A-G])(#|b|sharp)?$/)
    if (!m) return null
    const shift = m[2] === 'b' ? -1 : m[2] ? 1 : 0
    return (LETTER_PC[m[1]] + shift + 12) % 12
}

// chord-sheet suffix -> chords-db suffix, where they differ
const SUFFIXES: Record<string, string[]> = {
    '': ['major'],
    m: ['minor'],
    min: ['minor'],
    mi: ['minor'],
    '-': ['minor'],
    M7: ['maj7'],
    sus: ['sus', 'sus4'],
    '+': ['aug'],
    '°': ['dim'],
}

function groupFor(db: ChordDb, pc: number) {
    for (const [name, group] of Object.entries(db.chords)) {
        if (pitchClass(name) === pc) return group
    }
    return null
}

function spellings(pc: number): string[] {
    const sharps = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    const flats = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
    return [...new Set([sharps[pc], flats[pc]])]
}

/** Every library position for a chord name, best first; [] if none. */
export function lookupChord(db: ChordDb, chord: string): Fingering[] {
    const m = chord.trim().match(/^([A-G][#b]?)(.*?)(?:\/([A-G][#b]?))?$/)
    if (!m) return []
    const pc = pitchClass(m[1])
    const group = pc === null ? null : groupFor(db, pc)
    if (!group) return []
    const suffixes = SUFFIXES[m[2]] ?? [m[2]]
    const find = (suffix: string) => group.find((c) => c.suffix === suffix)?.positions ?? null

    if (m[3]) {
        const bassPc = pitchClass(m[3])
        const base = m[2] === '' ? '' : m[2] === 'm' ? 'm' : null
        if (bassPc !== null && base !== null) {
            for (const bass of spellings(bassPc)) {
                const found = find(`${base}/${bass}`)
                if (found) return found
            }
        }
    }
    for (const suffix of suffixes) {
        const found = find(suffix)
        if (found) return found
    }
    return []
}

export function fingeringFromDefine(d: ChordDefine): Fingering {
    return { baseFret: d.baseFret, frets: [...d.frets], fingers: [...d.fingers], barres: [] }
}

export function defineFromFingering(name: string, f: Fingering): ChordDefine {
    return { name, baseFret: f.baseFret, frets: [...f.frets], fingers: [...f.fingers] }
}

/** chords-db numbers strings from the lowest; svguitar from the highest (1). */
export function toSvguitar(f: Fingering, strings: number) {
    const barres = f.barres.map((fret) => {
        const on = f.frets.map((v, i) => (v === fret ? strings - i : null)).filter((s): s is number => s !== null)
        return { fromString: Math.max(...on), toString: Math.min(...on), fret }
    })
    const barred = new Set(f.barres)
    const fingers: [number, number | 'x'][] = []
    f.frets.forEach((fret, i) => {
        if (barred.has(fret)) return
        fingers.push([strings - i, fret < 0 ? 'x' : fret])
    })
    return { fingers, barres, position: f.baseFret }
}
