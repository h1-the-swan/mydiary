/**
 * One configured markdown-it for the whole app.
 *
 * Renders `#tag` and `#namespace:slug` in note text as links to the tag page,
 * with the same grammar as the backend's hashtags.py so both agree on what a
 * tag is: a bare slug needs a letter (`#1` is not a tag), a namespaced one
 * does not (`#day:2026-09-13` is), and nothing inside a link counts.
 *
 * The anchors are plain hrefs because they come out of v-html; the
 * `v-router-links` directive turns clicks on them into router navigations.
 */
import MarkdownIt from 'markdown-it'
import { normalizeKey, tagPath } from '@/tags'

// the same shape as the backend's HASHTAG_RE, anchored at the `#`
const L = '\\p{L}'
const WORD = `[\\p{L}\\p{N}_]`
const SLUG = `[\\p{L}\\p{N}_-]`
const HASHTAG = new RegExp(
    `^#(?:(${L}${SLUG}*):(${WORD}${SLUG}*)|((?=${SLUG}*${L})${WORD}${SLUG}*))(?![\\p{L}\\p{N}_:])`,
    'u'
)
// glued to a word, an HTML entity, a heading marker or a URL path: not a tag
const NOT_AFTER = /[\p{L}\p{N}_&#/]/u

// the few fields of markdown-it's inline state the rule touches
interface InlineState {
    src: string
    pos: number
    posMax: number
    linkLevel: number
    push(
        type: string,
        tag: string,
        nesting: 0 | 1 | -1
    ): { attrs: [string, string][] | null; content: string }
}

function hashtag(state: InlineState, silent: boolean): boolean {
    const start = state.pos
    if (state.src.charCodeAt(start) !== 0x23 /* # */) return false
    if (state.linkLevel > 0) return false
    if (start > 0 && NOT_AFTER.test(state.src[start - 1])) return false
    const m = HASHTAG.exec(state.src.slice(start, state.posMax))
    if (!m) return false
    const key = normalizeKey(m[0])
    if (!key) return false
    if (!silent) {
        const open = state.push('link_open', 'a', 1)
        open.attrs = [
            ['href', tagPath(key)],
            ['class', 'tag-link'],
        ]
        const text = state.push('text', '', 0)
        text.content = m[0]
        state.push('link_close', 'a', -1)
    }
    state.pos += m[0].length
    return true
}

export const md = new MarkdownIt()
md.inline.ruler.push(
    'hashtag',
    hashtag as unknown as Parameters<typeof md.inline.ruler.push>[1]
)
