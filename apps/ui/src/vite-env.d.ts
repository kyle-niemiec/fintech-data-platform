/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_RELEASE_TAG?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
