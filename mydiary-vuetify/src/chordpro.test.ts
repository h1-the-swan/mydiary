import { describe, expect, it } from 'vitest'
import {
    abbreviate,
    bracketedNonChords,
    convertChordsOverLyrics,
    copySheet,
    defineFromAbsoluteFrets,
    describeKey,
    formatDefine,
    isChord,
    keyName,
    type Level,
    lineSegments,
    parseChordLine,
    parseDefine,
    parseFretString,
    parseKey,
    parseSheet,
    sectionKeys,
    setChordDefine,
    setChordNote,
    shapeKey,
    skeleton,
    structure,
    suggestSections,
    transposeChord,
    transposeSheet,
    usesFlats,
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

describe('convertChordsOverLyrics', () => {
    it('merges chord lines into the lyric below', () => {
        const paste = ['[Verse 1]', 'C              G', 'Paper lanterns on the line', '', 'Chorus:', 'F        C', 'Hold the light'].join('\n')
        expect(convertChordsOverLyrics(paste)).toBe(
            ['[Verse 1]', '[C]Paper lanterns [G]on the line', '', '[Chorus]', '[F]Hold the [C]light', ''].join('\n')
        )
    })

    it('pads a lyric shorter than its chords', () => {
        expect(convertChordsOverLyrics('G       D\nOh')).toBe('[G]Oh      [D]\n')
    })

    it('keeps a chord line with no lyric as chords', () => {
        expect(convertChordsOverLyrics('[Intro]\nG  D  Em  C\n\n[Verse]\nwords')).toBe('[Intro]\n[G] [D] [Em] [C]\n\n[Verse]\nwords\n')
    })

    it('ignores bar lines and repeat marks when detecting chord lines', () => {
        expect(convertChordsOverLyrics('| G | D | x2')).toBe('[G] [D]\n')
    })

    it('strips tab-site markup', () => {
        expect(convertChordsOverLyrics('[tab][ch]G[/ch]\nhello[/tab]')).toBe('[G]hello\n')
    })

    it('does not mistake a lyric for chords', () => {
        expect(convertChordsOverLyrics('Am I wrong')).toBe('Am I wrong\n')
    })

    it('reads a lone chord-shaped word over a lyric as a chord, not the lyric', () => {
        // Ambiguous with a one-word lyric line that happens to be chord-shaped
        // ("A", "Am"); a bare chord at column 0 above a lyric is far more
        // common in a tab paste, so chords win. See the comment on chordColumns.
        expect(convertChordsOverLyrics('A\nWalking down the road')).toBe('[A]Walking down the road\n')
    })

    it('reads bars written without spaces as separate chords', () => {
        expect(convertChordsOverLyrics('C|G|Am|F')).toBe('[C] [G] [Am] [F]\n')
    })

    it('treats a trailing * marker as part of the chord, not the token', () => {
        expect(convertChordsOverLyrics('G   D   Em   C*\nHold the light')).toBe('[G]Hold[D] the[Em] ligh[C]t\n')
    })

    it('blanks out a parenthesised aside on a chord line', () => {
        expect(convertChordsOverLyrics('G       D      (let ring)\nOh what a day')).toBe('[G]Oh what [D]a day\n')
    })

    it('leaves a line of only parentheticals as a lyric', () => {
        expect(convertChordsOverLyrics('(oh) (yeah)')).toBe('(oh) (yeah)\n')
    })
})

describe('suggestSections', () => {
    it('labels verses and writes a repeated block once', () => {
        const plain = ['First verse line', 'second line', '', 'Hold the light', 'Hold it tight', '', 'Another verse', '', 'Hold the light', 'Hold it tight!'].join('\n')
        expect(suggestSections(plain)).toBe(
            ['[Verse 1]', 'First verse line', 'second line', '', '[Chorus?]', 'Hold the light', 'Hold it tight', '', '[Verse 2]', 'Another verse', '', '[Chorus?]', ''].join('\n')
        )
    })

    it('names a second repeated block differently', () => {
        const plain = 'a\n\nb\n\na\n\nb'
        expect(parseSheet(suggestSections(plain)).occurrences.map((o) => o.key)).toEqual(['Chorus?', 'Repeat 2?', 'Chorus?', 'Repeat 2?'])
    })
})

describe('bracketedNonChords', () => {
    it('finds alternate-lyric brackets but not chords or labels', () => {
        const sheet = '[Verse 1]\nFolding [holding] paper [G]cranes\n[Chorus]'
        expect(bracketedNonChords(sheet)).toEqual(['holding'])
    })
})

describe('keys', () => {
    it('parses and names keys', () => {
        expect(parseKey('Ab')).toEqual({ pc: 8, minor: false })
        expect(parseKey('F#m')).toEqual({ pc: 6, minor: true })
        expect(parseKey('H')).toBeNull()
        expect(keyName({ pc: 1, minor: false })).toBe('Db')
        expect(keyName({ pc: 1, minor: true })).toBe('C#m')
    })

    it('knows flat keys', () => {
        expect(['F', 'Bb', 'Ab', 'Dm', 'Ebm'].map(usesFlats)).toEqual([true, true, true, true, true])
        expect(['G', 'E', 'F#m', 'C'].map(usesFlats)).toEqual([false, false, false, false])
    })

    it('derives the shape key from sounding key and capo', () => {
        expect(shapeKey('Ab', 8)).toBe('C')
        expect(shapeKey('A', 2)).toBe('G')
        expect(shapeKey('F#m', 2)).toBe('Em')
        expect(shapeKey('G', null)).toBe('G')
        expect(shapeKey(null, 2)).toBeNull()
    })

    it('describes an arrangement', () => {
        expect(describeKey('Ab', 8)).toBe('Sounds in Ab · C shapes · capo 8')
        expect(describeKey('G', 0)).toBe('Key of G')
        expect(describeKey(null, 3)).toBe('Capo 3')
        expect(describeKey(null, null)).toBe('')
    })
})

describe('transposition', () => {
    it('moves roots and bass notes', () => {
        expect(transposeChord('G/B', 2, false)).toBe('A/C#')
        expect(transposeChord('F#m7', -1, false)).toBe('Fm7')
        expect(transposeChord('C', 3, true)).toBe('Eb')
        expect(transposeChord('N.C.', 3, true)).toBe('N.C.')
    })

    it('transposes chords in a sheet but not labels or directives', () => {
        const sheet = '{title: X}\n[Chorus]\n[G]Hold the [D/F#]light'
        expect(transposeSheet(sheet, 5, false)).toBe('{title: X}\n[Chorus]\n[C]Hold the [G/B]light')
    })

    it('copies a guitar sheet to ukulele by shape key and drops fingerings', () => {
        const sheet = '{define: C base-fret 1 frets x 3 2 0 1 0}\n{x_chordnote: C | full barre}\n[Verse 1]\n[C]Paper [F]lanterns'
        // guitar: sounds Ab with C shapes (capo 8); ukulele: plays in Ab, no capo
        expect(copySheet(sheet, { key: 'Ab', capo: 8 }, { key: 'Ab', capo: 0 })).toBe('[Verse 1]\n[Ab]Paper [Db]lanterns')
    })

    it('only strips directives when a key is unknown', () => {
        expect(copySheet('{define: C base-fret 1 frets 0 0 0 3}\n[C]x', { key: null }, { key: 'G' })).toBe('[C]x')
    })
})

describe('chord directives', () => {
    const def = { name: 'Am', baseFret: 1, frets: [2, 0, 0, 0], fingers: [2, 0, 0, 0] }

    it('formats a define', () => {
        expect(formatDefine({ ...def, frets: [-1, 0, 2, 2, 1, 0], fingers: [] })).toBe('{define: Am base-fret 1 frets x 0 2 2 1 0}')
    })

    it('adds, replaces and removes a define at the top of the sheet', () => {
        const sheet = '{title: X}\n[Verse 1]\n[Am]words'
        const added = setChordDefine(sheet, 'Am', def)
        expect(added).toBe('{title: X}\n{define: Am base-fret 1 frets 2 0 0 0 fingers 2 0 0 0}\n[Verse 1]\n[Am]words')
        const replaced = setChordDefine(added, 'Am', { ...def, frets: [2, 0, 0, 3] })
        expect(replaced).toContain('frets 2 0 0 3')
        expect(replaced.match(/define/g)).toHaveLength(1)
        expect(setChordDefine(replaced, 'Am', null)).toBe(sheet)
    })

    it('sets and clears a chord note', () => {
        const withNote = setChordNote('[G]x', 'G', ' ring finger on B ')
        expect(withNote).toBe('{x_chordnote: G | ring finger on B}\n[G]x')
        expect(setChordNote(withNote, 'G', '')).toBe('[G]x')
    })

    it('reads fret strings', () => {
        expect(parseFretString('x32010', 6)).toEqual([-1, 3, 2, 0, 1, 0])
        expect(parseFretString('10 12 12 11 10 10', 6)).toEqual([10, 12, 12, 11, 10, 10])
        expect(parseFretString('0003', 4)).toEqual([0, 0, 0, 3])
        expect(parseFretString('000', 4)).toBeNull()
    })

    it('makes a define from absolute frets', () => {
        expect(defineFromAbsoluteFrets('C', [-1, 3, 2, 0, 1, 0])).toEqual({ name: 'C', baseFret: 1, frets: [-1, 3, 2, 0, 1, 0], fingers: [] })
        expect(defineFromAbsoluteFrets('Bb', [6, 8, 8, 7, 6, 6])).toEqual({ name: 'Bb', baseFret: 6, frets: [1, 3, 3, 2, 1, 1], fingers: [] })
    })
})

describe('fading', () => {
    const line = parseChordLine('[C]Paper lanterns [G]on the line')
    const shown = (level: Level) =>
        lineSegments(line, level)
            .map((s) => s.runs.map((r) => (r.hidden ? '_'.repeat(r.text.length) : r.text)).join(''))
            .join('|')

    it('full shows everything', () => {
        expect(shown('full')).toBe('Paper lanterns |on the line')
    })
    // whitespace always shows, so a faded line keeps its word shapes
    it('letters shows first letters', () => {
        expect(shown('letters')).toBe('P____ l_______ |o_ t__ l___')
    })
    it('cues shows the first three words', () => {
        expect(shown('cues')).toBe('Paper lanterns |on ___ ____')
    })
    it('memorized hides all text but keeps chords', () => {
        expect(shown('memorized')).toBe('_____ ________ |__ ___ ____')
        expect(lineSegments(line, 'memorized').map((s) => s.chord)).toEqual(['C', 'G'])
    })
    it('adds a chordless leading segment', () => {
        expect(lineSegments(parseChordLine('Oh [G]yes'), 'full').map((s) => s.chord)).toEqual([null, 'G'])
    })
    it('never fades comments', () => {
        expect(lineSegments({ text: 'let ring', chords: [], comment: true }, 'memorized')[0].runs).toEqual([{ text: 'let ring', hidden: false }])
    })
})
