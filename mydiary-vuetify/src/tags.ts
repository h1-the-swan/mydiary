/**
 * Tag helpers mirroring the backend's hashtags.py and tags.py, so the UI can
 * normalise a typed key, build tag links, and label namespaces without a
 * round trip. The grammar lives in the backend; keep these in step with it.
 */
import type { RouteLocationRaw } from 'vue-router'
import type { TagNamespaceRead } from '@/api'

/** Lowercase letters, digits, `-` and `_`; anything else becomes a hyphen. */
export function slugifyTag(text: string): string {
    return (text || '')
        .normalize('NFKD')
        .replace(/[̀-ͯ]/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9_-]+/g, '-')
        .replace(/^[-_]+|[-_]+$/g, '')
}

export function tagKey(namespace: string, slug: string): string {
    return namespace ? `${namespace}:${slug}` : slug
}

/**
 * Split a typed key into its normalised halves. Only the first colon
 * separates the namespace. Returns null when nothing slug-shaped is left.
 */
export function parseKey(key: string): { namespace: string; slug: string } | null {
    const text = (key || '').trim().replace(/^#+/, '')
    const at = text.indexOf(':')
    const namespace = at >= 0 ? slugifyTag(text.slice(0, at)) : ''
    const slug = slugifyTag(at >= 0 ? text.slice(at + 1) : text)
    return slug ? { namespace, slug } : null
}

/** The key a hashtag match normalises to, or null when it does not. */
export function normalizeKey(key: string): string | null {
    const parsed = parseKey(key)
    return parsed ? tagKey(parsed.namespace, parsed.slug) : null
}

export function tagRoute(key: string): RouteLocationRaw {
    return { name: 'tag', params: { tagKey: key } }
}

export function tagPath(key: string): string {
    return `/tags/${encodeURIComponent(key)}`
}

/** Where a tag's target, or the thing it refers to, lives in the app. */
export function targetRoute(
    kind: string,
    id: string,
    frontendRoute?: string | null
): RouteLocationRaw | undefined {
    if (frontendRoute === 'MyDiaryDay') return { name: 'MyDiaryDay', query: { dt: id } }
    if (frontendRoute === 'performSong') return { name: 'performSong', params: { id } }
    return undefined
}

/**
 * Singular and plural labels for a namespace. Prefers what the backend
 * reports (the registry's labels), and title-cases anything unregistered.
 */
export function namespaceLabels(
    namespace: string,
    known?: TagNamespaceRead[] | null
): { label: string; plural: string } {
    const hit = known?.find((n) => n.namespace === namespace)
    if (hit) return { label: hit.label, plural: hit.plural }
    if (!namespace) return { label: 'Tag', plural: 'Tags' }
    const word = namespace
        .split(/[-_]+/)
        .filter(Boolean)
        .map((w) => w[0].toUpperCase() + w.slice(1))
        .join(' ')
    return { label: word, plural: `${word}s` }
}

/** Section heading for a namespace on the tags index. */
export function namespaceSectionLabel(
    namespace: string,
    known?: TagNamespaceRead[] | null
): string {
    return namespace ? namespaceLabels(namespace, known).plural : 'No namespace'
}

export function formatDay(dt: string): string {
    const parsed = new Date(`${dt}T00:00`)
    if (Number.isNaN(parsed.getTime())) return dt
    return parsed.toLocaleDateString(undefined, {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        year: 'numeric',
    })
}
