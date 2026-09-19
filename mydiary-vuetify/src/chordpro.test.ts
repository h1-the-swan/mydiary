import { describe, expect, it } from 'vitest'
import {
    abbreviate,
    isChord,
    parseChordLine,
    parseDefine,
    parseSheet,
    sectionKeys,
    skeleton,
    structure,
} from './chordpro'

const SHEET = `{title: Paper Lanterns}
{define: Am base-fret 1 frets 2 0 0 0 fingers 2 0 0 0}
{x_chordnote: Bm | easy version: Bm7}
[Verse 1]
[C]Paper lanterns [G]on the line
[Am]Folded paper, [F]borrowed time

[Chorus]
[F]Hold the [C]light
[G]Hold it [Am]tight

[Verse 2]
[C]Candle wax on [G]kitchen floors

[Chorus]

[Bridge]
[Bm]Somewhere else

{chorus}
`

describe('isChord', () => {
    it.each(['G', 'Am', 'F#m7', 'Bbmaj7', 'Dsus4', 'Cadd9', 'G/B', 'D/F#', 'E7b9', 'C#m7b5', 'N.C.', 'Em(maj7)', 'B7sus4', 'Ebm', 'Am7/G'])(
        '%s is a chord',
        (c) => expect(isChord(c)).toBe(true)
    )
    it.each(['Chorus', 'holding', 'Verse 1', 'x2', 'H', 'am'])('%s is not a chord', (c) =>
        expect(isChord(c)).toBe(false)
    )
})

describe('parseChordLine', () => {
    it('places chords at text offsets', () => {
        expect(parseChordLine('[C]Paper lanterns [G]on the line')).toEqual({
            text: 'Paper lanterns on the line',
            chords: [
                { chord: 'C', index: 0 },
                { chord: 'G', index: 15 },
            ],
        })
    })
})

describe('parseDefine', () => {
    it('reads base fret, frets and fingers', () => {
        expect(parseDefine('Bm base-fret 2 frets x 1 3 3 2 1 fingers 0 1 3 4 2 1')).toEqual({
            name: 'Bm',
            baseFret: 2,
            frets: [-1, 1, 3, 3, 2, 1],
            fingers: [0, 1, 3, 4, 2, 1],
        })
    })
    it('rejects a define without frets', () => {
        expect(parseDefine('Am base-fret 1')).toBeNull()
    })
})

describe('parseSheet', () => {
    const parsed = parseSheet(SHEET)

    it('splits sections by label and recalls empty repeats', () => {
        expect(parsed.occurrences.map((o) => [o.key, o.recalled])).toEqual([
            ['Verse 1', false],
            ['Chorus', false],
            ['Verse 2', false],
            ['Chorus', true],
            ['Bridge', false],
            ['Chorus', true],
        ])
        expect(parsed.occurrences[3].lines).toEqual(parsed.occurrences[1].lines)
    })

    it('trims blank lines at section edges', () => {
        expect(parsed.occurrences[0].lines.map((l) => l.text)).toEqual([
            'Paper lanterns on the line',
            'Folded paper, borrowed time',
        ])
    })

    it('collects defines, chord notes, meta and chords in order', () => {
        expect(parsed.defines.Am.frets).toEqual([2, 0, 0, 0])
        expect(parsed.chordNotes).toEqual({ Bm: 'easy version: Bm7' })
        expect(parsed.meta.title).toBe('Paper Lanterns')
        expect(parsed.chords).toEqual(['C', 'G', 'Am', 'F', 'Bm'])
    })

    it('reads start_of directives with and without labels', () => {
        const p = parseSheet('{start_of_verse: Verse 1}\nla\n{end_of_verse}\n{soc}\nhey\n{eoc}')
        expect(p.occurrences.map((o) => o.key)).toEqual(['Verse 1', 'Chorus'])
    })

    it('puts unlabelled lines in the implicit section', () => {
        expect(parseSheet('just words\nmore words').occurrences.map((o) => o.key)).toEqual(['Song'])
        expect(parseSheet('').occurrences).toEqual([])
    })

    it('keeps comments as comment lines', () => {
        const p = parseSheet('[Intro]\n{c: let ring}')
        expect(p.occurrences[0].lines[0]).toEqual({ text: 'let ring', chords: [], comment: true })
    })

    it('treats a lone chord in brackets as a chord line, not a label', () => {
        const p = parseSheet('[Intro]\n[G]')
        expect(p.occurrences.map((o) => o.key)).toEqual(['Intro'])
        expect(p.occurrences[0].lines[0].chords).toEqual([{ chord: 'G', index: 0 }])
    })
})

describe('structure', () => {
    it('abbreviates labels', () => {
        expect(['Verse 1', 'Chorus', 'Pre-chorus', 'Final chorus', 'Chorus?', 'Song'].map(abbreviate)).toEqual([
            'V1', 'C', 'PC', 'FC', 'C?', 'S',
        ])
    })

    it('compresses consecutive repeats', () => {
        const p = parseSheet('[Verse 1]\na\n[Verse 2]\nb\n[Chorus]\nc\n[Verse 3]\nd\n[Chorus]\n[Bridge]\ne\n[Chorus]\n[Chorus]')
        expect(skeleton(p)).toBe('V1 V2 C V3 C B C×2')
        expect(structure(p).at(-1)).toEqual({ key: 'Chorus', abbr: 'C', count: 2, index: 6 })
    })

    it('lists unique section keys in order', () => {
        expect(sectionKeys(parseSheet(SHEET))).toEqual(['Verse 1', 'Chorus', 'Verse 2', 'Bridge'])
    })
})
