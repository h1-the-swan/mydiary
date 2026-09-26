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

// --- importing a sheet ------------------------------------------------------

const SECTION_WORDS =
    'intro|verse|pre-?chorus|chorus|post-?chorus|bridge|outro|refrain|interlude|solo|instrumental|coda|hook|break|tag'
const PASTE_LABEL_RE = new RegExp(`^\\s*\\[?\\s*((?:${SECTION_WORDS})(?:\\s*\\d+)?)\\s*\\]?\\s*:?\\s*$`, 'i')
// tokens a tab puts on a chord line that are not chords
const NOISE_TOKEN_RE = /^(?:\||\/|-+|x\d+|\(x\d+\)|\.{2,3})$/i

// A one-word lyric that happens to be chord-shaped ("A", "Am") is
// indistinguishable from a lone chord above the next line; a bare chord at
// column 0 over a lyric line is far more common in a tab paste than a
// one-word lyric line, so this reads it as a chord. See
// convertChordsOverLyrics's "reads a lone chord-shaped word over a lyric
// as a chord, not the lyric" test.
function chordColumns(line: string): ChordAt[] | null {
    // Blank out parenthesised asides ("(let ring)") before tokenising, so they
    // can't be mistaken for lyric words, but keep every other token's column
    // position intact.
    const blanked = line.replace(/\([^)]*\)/g, (m) => ' '.repeat(m.length))
    const out: ChordAt[] = []
    // Tokenise on runs of anything but whitespace or '|', so bars written
    // without surrounding spaces ("C|G|Am|F") still split into separate
    // chord tokens at their real columns.
    for (const m of blanked.matchAll(/[^\s|]+/g)) {
        const token = m[0]
        if (NOISE_TOKEN_RE.test(token)) continue
        const chord = token.replace(/\*+$/, '') // trailing '*' markers, e.g. "C*"
        if (!chord || !isChord(chord)) return null
        out.push({ chord, index: m.index! })
    }
    return out.length ? out : null
}

function tidyLabel(label: string): string {
    const t = label.trim().replace(/\s+/g, ' ')
    return t.charAt(0).toUpperCase() + t.slice(1).toLowerCase()
}

function placeChords(lyric: string, chords: ChordAt[]): string {
    let out = lyric
    for (const { chord, index } of [...chords].sort((a, b) => b.index - a.index)) {
        out = out.padEnd(index, ' ')
        out = out.slice(0, index) + `[${chord}]` + out.slice(index)
    }
    return out.replace(/\s+$/, '')
}

/** A chords-over-lyrics paste from a tab site, as ChordPro. */
export function convertChordsOverLyrics(paste: string): string {
    const lines = (paste || '')
        .replace(/\r\n?/g, '\n')
        .replace(/\[\/?(?:ch|tab)\]/g, '')
        .split('\n')
        .map((l) => l.replace(/\t/g, '    ').replace(/\s+$/, ''))
    const out: string[] = []
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i]
        const label = line.match(PASTE_LABEL_RE)
        if (label) {
            out.push(`[${tidyLabel(label[1])}]`)
            continue
        }
        const chords = chordColumns(line)
        if (!chords) {
            out.push(line)
            continue
        }
        const next = lines[i + 1]
        if (next !== undefined && next.trim() && !chordColumns(next) && !PASTE_LABEL_RE.test(next)) {
            out.push(placeChords(next, chords))
            i++
        } else {
            out.push(chords.map((c) => `[${c.chord}]`).join(' '))
        }
    }
    return out.join('\n').replace(/\n{3,}/g, '\n\n').trim() + '\n'
}

function normalizeBlock(lines: string[]): string {
    return lines
        .map((l) => l.toLowerCase().replace(/[^\p{L}\p{N}\s']/gu, '').replace(/\s+/g, ' ').trim())
        .join('\n')
}

/**
 * Plain lyrics (e.g. from LRCLIB) as labelled ChordPro. Stanzas are the
 * blank-line blocks; a block that appears more than once is probably a chorus,
 * so it is written once and later appearances are bare labels that recall it.
 * Labels end in "?" until the user confirms them.
 */
export function suggestSections(plain: string): string {
    const blocks = (plain || '')
        .replace(/\r\n?/g, '\n')
        .split(/\n\s*\n/)
        .map((b) => b.split('\n').map((l) => l.trim()).filter(Boolean))
        .filter((b) => b.length)
    const counts = new Map<string, number>()
    for (const b of blocks) {
        const n = normalizeBlock(b)
        counts.set(n, (counts.get(n) ?? 0) + 1)
    }
    const labels = new Map<string, string>()
    let verses = 0
    let repeats = 0
    const sections: string[] = []
    for (const b of blocks) {
        const n = normalizeBlock(b)
        const known = labels.get(n)
        if (known) {
            sections.push(`[${known}]`)
            continue
        }
        let label: string
        if ((counts.get(n) ?? 0) > 1) {
            repeats += 1
            label = repeats === 1 ? 'Chorus?' : `Repeat ${repeats}?`
        } else {
            verses += 1
            label = `Verse ${verses}`
        }
        labels.set(n, label)
        sections.push([`[${label}]`, ...b].join('\n'))
    }
    return sections.join('\n\n') + '\n'
}

/** Bracketed text ChordPro would read as a chord but isn't one, e.g. an alternate lyric. */
export function bracketedNonChords(sheet: string): string[] {
    const found = new Set<string>()
    for (const line of (sheet || '').split('\n')) {
        if (DIRECTIVE_RE.test(line) || LABEL_RE.test(line)) continue
        for (const m of line.matchAll(/\[([^\]]*)\]/g)) {
            if (!isChord(m[1])) found.add(m[1])
        }
    }
    return [...found]
}

// --- keys and transposition --------------------------------------------------

const SHARP_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
const FLAT_NAMES = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
const LETTER_PC: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 }
// the usual spelling of each key
const MAJOR_KEYS = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
const MINOR_KEYS = ['Cm', 'C#m', 'Dm', 'Ebm', 'Em', 'Fm', 'F#m', 'Gm', 'G#m', 'Am', 'Bbm', 'Bm']
const FLAT_KEYS_WITHOUT_B = new Set(['F', 'Dm', 'Gm', 'Cm', 'Fm'])

export interface KeyInfo {
    pc: number // pitch class, C = 0
    minor: boolean
}

const mod12 = (n: number) => ((n % 12) + 12) % 12

function pitchClass(note: string): number | null {
    const m = note.match(/^([A-G])([#b]?)$/)
    if (!m) return null
    return mod12(LETTER_PC[m[1]] + (m[2] === '#' ? 1 : m[2] === 'b' ? -1 : 0))
}

export function parseKey(key?: string | null): KeyInfo | null {
    const m = (key || '').trim().match(/^([A-G][#b]?)\s*(m|min|minor)?$/)
    if (!m) return null
    const pc = pitchClass(m[1])
    return pc === null ? null : { pc, minor: Boolean(m[2]) }
}

export function keyName(k: KeyInfo): string {
    return (k.minor ? MINOR_KEYS : MAJOR_KEYS)[k.pc]
}

export function usesFlats(key?: string | null): boolean {
    const k = parseKey(key)
    if (!k) return false
    const name = keyName(k)
    return name.includes('b') || FLAT_KEYS_WITHOUT_B.has(name)
}

export function transposeNote(note: string, semitones: number, flats: boolean): string {
    const pc = pitchClass(note)
    if (pc === null) return note
    return (flats ? FLAT_NAMES : SHARP_NAMES)[mod12(pc + semitones)]
}

export function transposeChord(chord: string, semitones: number, flats: boolean): string {
    if (!isChord(chord) || /^N\.?C/.test(chord)) return chord
    const m = chord.match(/^([A-G][#b]?)(.*?)(?:\/([A-G][#b]?))?$/)
    if (!m) return chord
    const bass = m[3] ? '/' + transposeNote(m[3], semitones, flats) : ''
    return transposeNote(m[1], semitones, flats) + m[2] + bass
}

/** The key of the shapes fingered: sounding key minus the capo. */
export function shapeKey(key?: string | null, capo?: number | null): string | null {
    const k = parseKey(key)
    if (!k) return null
    return keyName({ pc: mod12(k.pc - (capo ?? 0)), minor: k.minor })
}

export function describeKey(key?: string | null, capo?: number | null): string {
    const shapes = shapeKey(key, capo)
    if (key && shapes && capo) return `Sounds in ${key} · ${shapes} shapes · capo ${capo}`
    if (key) return `Key of ${key}`
    if (capo) return `Capo ${capo}`
    return ''
}

function mapLines(sheet: string, fn: (line: string) => string): string {
    return (sheet || '').split('\n').map(fn).join('\n')
}

export function transposeSheet(sheet: string, semitones: number, flats: boolean): string {
    return mapLines(sheet, (line) => {
        if (DIRECTIVE_RE.test(line) || (LABEL_RE.test(line) && !isChord(line.match(LABEL_RE)![1]))) return line
        return line.replace(CHORD_TOKEN_RE, (whole, chord: string) =>
            isChord(chord) ? `[${transposeChord(chord.trim(), semitones, flats)}]` : whole
        )
    })
}

const CHORD_DIRECTIVE_RE = /^\s*\{\s*(define|x_chordnote)\s*:/i

export function stripChordDirectives(sheet: string): string {
    return (sheet || '')
        .split('\n')
        .filter((line) => !CHORD_DIRECTIVE_RE.test(line))
        .join('\n')
}

type KeyAndCapo = { key?: string | null; capo?: number | null }

/**
 * One instrument's sheet made into a starting point for another. Chords move
 * by the difference in shape key; fingerings and chord notes are dropped,
 * since they belong to the instrument they were written for.
 */
export function copySheet(sheet: string, from: KeyAndCapo, to: KeyAndCapo): string {
    const stripped = stripChordDirectives(sheet)
    const fromShapes = parseKey(shapeKey(from.key, from.capo))
    const toShapesName = shapeKey(to.key, to.capo)
    const toShapes = parseKey(toShapesName)
    if (!fromShapes || !toShapes) return stripped
    return transposeSheet(stripped, mod12(toShapes.pc - fromShapes.pc), usesFlats(toShapesName))
}

// --- chord directives --------------------------------------------------------

export function formatDefine(d: ChordDefine): string {
    const frets = d.frets.map((f) => (f < 0 ? 'x' : String(f))).join(' ')
    const fingers = d.fingers.length ? ` fingers ${d.fingers.join(' ')}` : ''
    return `{define: ${d.name} base-fret ${d.baseFret} frets ${frets}${fingers}}`
}

function directiveChord(line: string, directive: string): string | null {
    const m = line.match(DIRECTIVE_RE)
    if (!m || m[1].toLowerCase() !== directive) return null
    const value = (m[2] ?? '').trim()
    return (directive === 'x_chordnote' ? value.split('|')[0] : value.split(/\s+/)[0]).trim()
}

function setChordDirective(sheet: string, directive: string, chord: string, line: string | null): string {
    const lines = (sheet || '').split('\n')
    const at = lines.findIndex((l) => directiveChord(l, directive) === chord)
    if (at >= 0) {
        if (line === null) lines.splice(at, 1)
        else lines[at] = line
        return lines.join('\n')
    }
    if (line === null) return sheet
    // new directives join the block at the top, before the first section
    let insert = 0
    while (insert < lines.length) {
        const m = lines[insert].match(DIRECTIVE_RE)
        if (!m || sectionStart(m[1].toLowerCase(), (m[2] ?? '').trim())) break
        insert++
    }
    lines.splice(insert, 0, line)
    return lines.join('\n')
}

export function setChordDefine(sheet: string, chord: string, d: ChordDefine | null): string {
    return setChordDirective(sheet, 'define', chord, d ? formatDefine({ ...d, name: chord }) : null)
}

export function setChordNote(sheet: string, chord: string, note: string | null): string {
    const text = (note ?? '').trim()
    return setChordDirective(sheet, 'x_chordnote', chord, text ? `{x_chordnote: ${chord} | ${text}}` : null)
}

/** "x32010" or "10 12 12 11 10 10" as absolute frets, lowest string first. */
export function parseFretString(s: string, strings: number): number[] | null {
    const t = s.trim()
    const parts = /[\s,]/.test(t) ? t.split(/[\s,]+/) : t.split('')
    if (parts.length !== strings) return null
    const frets = parts.map((p) => (/^[xX-]$/.test(p) ? -1 : Number(p)))
    return frets.some((n) => !Number.isInteger(n) || n < -1 || n > 24) ? null : frets
}

export function defineFromAbsoluteFrets(name: string, abs: number[]): ChordDefine {
    const fretted = abs.filter((f) => f > 0)
    const baseFret = fretted.length && Math.max(...fretted) > 4 ? Math.min(...fretted) : 1
    return { name, baseFret, frets: abs.map((f) => (f > 0 ? f - baseFret + 1 : f)), fingers: [] }
}

// --- fading -----------------------------------------------------------------

export interface Run {
    text: string
    hidden: boolean
}

export interface Segment {
    chord: string | null // the chord above this stretch of text
    runs: Run[]
}

const WORD_RE = /[\p{L}\p{N}'’]+/gu
// how many words a line keeps at the `cues` level
const CUE_WORDS = 3

/** Which characters of a line stay visible at a level. */
export function visibleMask(text: string, level: Level): boolean[] {
    // whitespace is always "visible": it looks the same either way, and it
    // keeps the hidden-text underline broken into word shapes
    // indexed by UTF-16 unit, like the chord offsets
    const mask: boolean[] = Array.from({ length: text.length }, (_, i) => level === 'full' || /\s/.test(text[i]))
    if (level === 'full' || level === 'memorized') return mask
    const words = [...text.matchAll(WORD_RE)]
    if (level === 'letters') {
        for (const w of words) mask[w.index!] = true
        return mask
    }
    const last = words[Math.min(CUE_WORDS, words.length) - 1]
    if (last) mask.fill(true, 0, last.index! + last[0].length)
    return mask
}

function toRuns(text: string, mask: boolean[]): Run[] {
    const runs: Run[] = []
    for (let i = 0; i < text.length; i++) {
        const hidden = !mask[i]
        const last = runs.at(-1)
        if (last && last.hidden === hidden) last.text += text[i]
        else runs.push({ text: text[i], hidden })
    }
    return runs
}

/** A line cut at its chords, each piece's text split into shown and hidden runs.
 *  Hidden text keeps its width, so chords stay over the right syllable. */
export function lineSegments(line: SheetLine, level: Level): Segment[] {
    const mask = line.comment ? new Array(line.text.length).fill(true) : visibleMask(line.text, level)
    const bounds: { chord: string | null; from: number }[] = []
    if (!line.chords.length || line.chords[0].index > 0) bounds.push({ chord: null, from: 0 })
    for (const c of line.chords) bounds.push({ chord: c.chord, from: c.index })
    return bounds.map((b, i) => {
        const to = i + 1 < bounds.length ? bounds[i + 1].from : line.text.length
        return { chord: b.chord, runs: toRuns(line.text.slice(b.from, to), mask.slice(b.from, to)) }
    })
}
