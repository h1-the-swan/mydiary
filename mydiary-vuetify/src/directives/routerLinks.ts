/**
 * `v-router-links`: make plain `<a href="/...">` anchors inside an element
 * navigate through vue-router instead of reloading the page. For markup that
 * Vue did not render, chiefly Markdown put in with v-html.
 *
 * Only a plain left click is intercepted. Modified clicks (open in a new
 * tab), anchors with a target, and anything that is not an app-relative
 * path keep their native behaviour.
 */
import type { Directive } from 'vue'
import type { Router } from 'vue-router'

const HANDLER = Symbol('routerLinks')

type Host = HTMLElement & { [HANDLER]?: (event: MouseEvent) => void }

export function routerLinksDirective(router: Router): Directive<Host> {
    return {
        mounted(el) {
            const handler = (event: MouseEvent) => {
                if (event.defaultPrevented || event.button !== 0) return
                if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
                const anchor = (event.target as Element | null)?.closest?.('a')
                if (!anchor || !el.contains(anchor)) return
                if (anchor.target && anchor.target !== '_self') return
                const href = anchor.getAttribute('href')
                if (!href || !href.startsWith('/') || href.startsWith('//')) return
                event.preventDefault()
                router.push(href)
            }
            el.addEventListener('click', handler)
            el[HANDLER] = handler
        },
        unmounted(el) {
            if (el[HANDLER]) el.removeEventListener('click', el[HANDLER])
            delete el[HANDLER]
        },
    }
}
