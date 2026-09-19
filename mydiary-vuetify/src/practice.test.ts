import { describe, expect, it } from 'vitest'
import { capoOrNull } from './practice'

describe('capoOrNull', () => {
    it('reads a cleared or missing field as no capo', () => {
        expect(capoOrNull('')).toBeNull()
        expect(capoOrNull(null)).toBeNull()
        expect(capoOrNull(undefined)).toBeNull()
        expect(capoOrNull(NaN)).toBeNull()
    })

    it('rejects values that are not whole numbers', () => {
        expect(capoOrNull(1.5)).toBeNull()
        expect(capoOrNull('abc')).toBeNull()
    })

    it('keeps an integer, including one typed as text', () => {
        expect(capoOrNull(0)).toBe(0)
        expect(capoOrNull(3)).toBe(3)
        expect(capoOrNull('2')).toBe(2)
    })
})
