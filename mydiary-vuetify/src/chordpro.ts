/**
 * ChordPro for the song sheets: parsing and structure (this task), the tab
 * paste import, transposition, directive editing and the practice fading.
 *
 * Only the subset the sheets use. Sections are `[Label]` lines or
 * `{start_of_*: Label}` directives; chords sit inline as `[G]`; fingerings are
 * `{define}` and chord notes the custom `{x_chordnote: Bm | ...}`. The backend
 * stores sheets as opaque text, so this is the only parser.
 */

// from the most help to the least; mirrors LEVELS in the backend's song_practice.py
export const LEVELS = ['full', 'letters', 'cues', 'memorized'] as const
export type Level = (typeof LEVELS)[number]

// lines that come before any section label belong to this one
export const IMPLICIT_SECTION = 'Song'

export interface ChordAt {
    chord: string
    index: number // offset into the line's text the chord sits above
}

export interface SheetLine {
    text: string
    chords: ChordAt[]
    comment?: boolean
}

export interface SectionOccurrence {
    key: string // the label as written; practice history is keyed on it
    lines: SheetLine[]
    recalled: boolean // an empty repeat, filled from the first with that label
}

export interface ChordDefine {
    name: string
    baseFret: number
    // relative to baseFret (1 = the base fret), 0 open, -1 muted; lowest string first
    frets: number[]
    fingers: number[]
}

export interface ParsedSheet {
    occurrences: SectionOccurrence[]
    defines: Record<string, ChordDefine>
    chordNotes: Record<string, string>
    chords: string[] // every chord used, in order of first appearance
    meta: Record<string, string>
}

export interface StructureItem {
    key: string
    abbr: string
    count: number // consecutive repeats folded into this item
    index: number // occurrence index of the first of them
}

const CHORD_RE =
    /^(?:N\.?C\.?|[A-G][#b]?(?:maj|min|mi|m|M|dim|aug|sus|add|°|ø|\+|-)?\d{0,2}(?:(?:maj|sus|add|no|b|#|\+|-)\d{1,2})*(?:\([^)]*\))?(?:\/[A-G][#b]?)?)$/
export const DIRECTIVE_RE = /^\s*\{\s*([A-Za-z_]+)\s*(?::\s*(.*?))?\s*\}\s*$/
export const LABEL_RE = /^\s*\[([^\]]+)\]\s*$/
const CHORD_TOKEN_RE = /\[([^\]]*)\]/g

const SECTION_DEFAULTS: Record<string, string> = {
    chorus: 'Chorus',
    verse: 'Verse',
    bridge: 'Bridge',
    tab: 'Tab',
    grid: 'Grid',
}
const SHORT_START: Record<string, string> = {
    soc: 'chorus',
    sov: 'verse',
    sob: 'bridge',
    sot: 'tab',
    sog: 'grid',
}
const COMMENT_DIRECTIVES = new Set(['comment', 'c', 'ci', 'comment_italic'])

export function isChord(token: string): boolean {
    return CHORD_RE.test(token.trim())
}

/** The section a directive starts, or null if it starts none. */
export function sectionStart(name: string, value: string): string | null {
    const kind = name.startsWith('start_of_') ? name.slice('start_of_'.length) : SHORT_START[name]
    if (kind) return value || SECTION_DEFAULTS[kind] || kind.charAt(0).toUpperCase() + kind.slice(1)
    if (name === 'chorus') return value || 'Chorus'
    return null
}

export function parseChordLine(raw: string): SheetLine {
    const chords: ChordAt[] = []
    let text = ''
    let last = 0
    for (const m of raw.matchAll(CHORD_TOKEN_RE)) {
        text += raw.slice(last, m.index)
        chords.push({ chord: m[1].trim(), index: text.length })
        last = m.index! + m[0].length
    }
    text += raw.slice(last)
    return { text, chords }
}

export function parseDefine(value: string): ChordDefine | null {
    const tokens = value.trim().split(/\s+/)
    const name = tokens.shift()
    if (!name) return null
    let baseFret = 1
    const frets: number[] = []
    const fingers: number[] = []
    let mode: 'frets' | 'fingers' | null = null
    for (let i = 0; i < tokens.length; i++) {
        const t = tokens[i].toLowerCase()
        if (t === 'base-fret') {
            baseFret = parseInt(tokens[++i] ?? '1', 10) || 1
            mode = null
        } else if (t === 'frets' || t === 'fingers') {
            mode = t
        } else if (mode === 'frets') {
            frets.push(t === 'x' || t === 'n' ? -1 : parseInt(t, 10))
        } else if (mode === 'fingers') {
            fingers.push(parseInt(t, 10) || 0)
        }
    }
    if (!frets.length || frets.some(Number.isNaN)) return null
    return { name, baseFret, frets, fingers }
}

function isBlank(line: SheetLine): boolean {
    return !line.text.trim() && !line.chords.length && !line.comment
}

function trimBlankLines(lines: SheetLine[]): SheetLine[] {
    let start = 0
    let end = lines.length
    while (start < end && isBlank(lines[start])) start++
    while (end > start && isBlank(lines[end - 1])) end--
    return lines.slice(start, end)
}

function startSection(parsed: ParsedSheet, key: string): SectionOccurrence {
    const occ: SectionOccurrence = { key, lines: [], recalled: false }
    parsed.occurrences.push(occ)
    return occ
}

export function parseSheet(sheet: string): ParsedSheet {
    const parsed: ParsedSheet = { occurrences: [], defines: {}, chordNotes: {}, chords: [], meta: {} }
    let current: SectionOccurrence | null = null

    for (const raw of (sheet || '').replace(/\r\n?/g, '\n').split('\n')) {
        const line = raw.replace(/\s+$/, '')
        const directive = line.match(DIRECTIVE_RE)
        if (directive) {
            const name = directive[1].toLowerCase()
            const value = (directive[2] ?? '').trim()
            const started = sectionStart(name, value)
            if (started) {
                current = startSection(parsed, started)
            } else if (name.startsWith('end_of_') || /^eo[cvbtg]$/.test(name)) {
                // a section runs until the next label, so ends carry nothing
            } else if (name === 'define') {
                const d = parseDefine(value)
                if (d) parsed.defines[d.name] = d
            } else if (name === 'x_chordnote') {
                const [chord, ...note] = value.split('|')
                if (chord.trim()) parsed.chordNotes[chord.trim()] = note.join('|').trim()
            } else if (COMMENT_DIRECTIVES.has(name)) {
                current = current ?? startSection(parsed, IMPLICIT_SECTION)
                current.lines.push({ text: value, chords: [], comment: true })
            } else {
                parsed.meta[name] = value
            }
            continue
        }
        const label = line.match(LABEL_RE)
        if (label && !isChord(label[1])) {
            current = startSection(parsed, label[1].trim())
            continue
        }
        if (!current) {
            if (!line.trim()) continue
            current = startSection(parsed, IMPLICIT_SECTION)
        }
        current.lines.push(parseChordLine(line))
    }

    const firstLines: Record<string, SheetLine[]> = {}
    for (const occ of parsed.occurrences) {
        occ.lines = trimBlankLines(occ.lines)
        if (occ.lines.length && !(occ.key in firstLines)) firstLines[occ.key] = occ.lines
    }
    for (const occ of parsed.occurrences) {
        if (!occ.lines.length && firstLines[occ.key]) {
            occ.lines = firstLines[occ.key]
            occ.recalled = true
        }
    }

    const seen = new Set<string>()
    for (const occ of parsed.occurrences) {
        for (const line of occ.lines) {
            for (const { chord } of line.chords) {
                if (chord && !seen.has(chord)) {
                    seen.add(chord)
                    parsed.chords.push(chord)
                }
            }
        }
    }
    return parsed
}

export function sectionKeys(parsed: ParsedSheet): string[] {
    return [...new Set(parsed.occurrences.map((o) => o.key))]
}

/** "Verse 1" -> "V1", "Pre-chorus" -> "PC", "Chorus?" -> "C?". */
export function abbreviate(label: string): string {
    const question = label.trim().endsWith('?') ? '?' : ''
    const words = label.trim().replace(/\?$/, '').split(/[\s-]+/).filter(Boolean)
    const letters = words.filter((w) => !/^\d+$/.test(w)).map((w) => w[0].toUpperCase()).join('')
    const digits = words.filter((w) => /^\d+$/.test(w)).join('')
    return letters + digits + question
}

export function structure(parsed: ParsedSheet): StructureItem[] {
    const items: StructureItem[] = []
    parsed.occurrences.forEach((occ, index) => {
        const last = items.at(-1)
        if (last && last.key === occ.key) last.count += 1
        else items.push({ key: occ.key, abbr: abbreviate(occ.key), count: 1, index })
    })
    return items
}

export function skeleton(parsed: ParsedSheet): string {
    return structure(parsed)
        .map((s) => (s.count > 1 ? `${s.abbr}×${s.count}` : s.abbr))
        .join(' ')
}
