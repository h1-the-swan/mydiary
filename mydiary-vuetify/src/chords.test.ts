import { describe, expect, it } from 'vitest'
import { defineFromFingering, fingeringFromDefine, loadChordDb, lookupChord, toSvguitar } from './chords'

const guitar = await loadChordDb('guitar')
const ukulele = await loadChordDb('ukulele')

describe('lookupChord', () => {

    it('finds a major chord by pitch class whatever the spelling', () => {
        expect(lookupChord(ukulele, 'A')[0].frets).toEqual([2, 1, 0, 0])
        expect(lookupChord(guitar, 'Db').length).toBeGreaterThan(0) // stored as Csharp
        expect(lookupChord(ukulele, 'C#').length).toBeGreaterThan(0) // stored as Db
    })

    it('maps suffixes', () => {
        expect(lookupChord(ukulele, 'Am')[0].frets).toEqual([2, 0, 0, 0])
        expect(lookupChord(guitar, 'Cmaj7').length).toBeGreaterThan(0)
        expect(lookupChord(ukulele, 'Esus').length).toBeGreaterThan(0) // no plain sus on ukulele: sus4
    })

    it('uses slash chords when the library has them and drops the bass otherwise', () => {
        expect(lookupChord(guitar, 'C/E').length).toBeGreaterThan(0)
        expect(lookupChord(ukulele, 'G/B')).toEqual(lookupChord(ukulele, 'G'))
    })

    it('returns nothing for a non-chord', () => {
        expect(lookupChord(guitar, 'Chorus')).toEqual([])
    })
})

describe('conversions', () => {
    it('turns a define into a fingering and back', () => {
        const d = { name: 'Bb', baseFret: 6, frets: [1, 3, 3, 2, 1, 1], fingers: [1, 3, 4, 2, 1, 1] }
        const f = fingeringFromDefine(d)
        expect(f).toEqual({ baseFret: 6, frets: [1, 3, 3, 2, 1, 1], fingers: [1, 3, 4, 2, 1, 1], barres: [] })
        expect(defineFromFingering('Bb', f)).toEqual(d)
    })

    it('numbers strings from the highest, as svguitar does', () => {
        const out = toSvguitar({ baseFret: 1, frets: [-1, 3, 2, 0, 1, 0], fingers: [], barres: [] }, 6)
        expect(out.fingers).toEqual([[6, 'x'], [5, 3], [4, 2], [3, 0], [2, 1], [1, 0]])
        expect(out.position).toBe(1)
    })

    it('spans a barre across the strings at its fret', () => {
        const out = toSvguitar({ baseFret: 1, frets: [1, 3, 3, 2, 1, 1], fingers: [1, 3, 4, 2, 1, 1], barres: [1] }, 6)
        expect(out.barres).toEqual([{ fromString: 6, toString: 1, fret: 1 }])
        expect(out.fingers.filter(([, fret]) => fret === 1)).toEqual([])
    })
})
