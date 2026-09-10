/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Free CARTO basemap key; without it the tiles come back watermarked. */
  readonly VITE_CARTO_BASEMAP_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
