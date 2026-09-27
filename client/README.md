# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

## Backend endpoint

The SPA reaches the FastAPI API through `VITE_API_BASE_URL`, read by
`src/shared/api/client.ts`. Vite loads it from the mode-specific env files in
this directory:

| File               | `VITE_API_BASE_URL`            | Used by                                       |
| ------------------ | ------------------------------ | --------------------------------------------- |
| `.env.development` | `http://127.0.0.1:8000/api/v1` | `pnpm dev`                                    |
| `.env.production`  | `/api/v1`                      | `pnpm build`, `pnpm preview`, deployed bundle |

`pnpm dev` serves the SPA on :5173, a different origin from the API, so its
value is absolute and relies on the backend CORS policy. The production value
stays relative because FastAPI serves the built bundle itself (`app.frontend`
mounts the SPA at `/`): one build then works at `127.0.0.1:8000` and on the
Databricks Apps domain.

Override either mode per machine with `.env.development.local` or
`.env.production.local`; both are git-ignored through `*.local`.

## Access token header

The access token is sent in the header the API reports through `/healthz`
(`token.header` in `server/config/config.default.yaml`, `X-Bearer-Token` by
default). `getServiceStatus()` caches that name in `sessionStorage` before the
first authenticated call, and `DEFAULT_TOKEN_HEADER` covers the moment before it
is known. A platform proxy such as the Databricks Apps SSO layer owns
`Authorization`, so the API prefers this dedicated header and only accepts
`Authorization: Bearer` as a fallback for plain API clients.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
