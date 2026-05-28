/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_RELEASE_TAG?: string;
  readonly VITE_APP_ENV?: string;
  readonly VITE_LAUNCHER_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
