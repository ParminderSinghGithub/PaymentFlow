/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_PAYMENTFLOW_API_URL?: string;
  readonly VITE_MERCHANT_STOREFRONT_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
