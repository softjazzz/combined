# Health QC Monorepo

- apps/
  - medqc-web/: Migrated MedQC frontend
  - yibao-web/: Placeholder for Yibao frontend
  - edge-functions/: Shared function sources
- packages/
  - ui-qc/: Shared QC UI components
  - web-utils/: Shared utilities (api-wrapper, date-utils, rules-validator)
  - rule-engine/: Shared rule evaluation library (Deno/Node)
  - supabase-kit/: Edge functions helpers (CORS/auth/errors)
  - schemas/: Shared TS types (DB/OpenAPI)
- infra/
  - supabase/: Unified migrations (yibao_* and medical_*/llm_*)
  - pdf-service/: Python PDF extraction service

## Develop

pnpm install
pnpm dev

## Documentation

- See docs/Monorepo-Integration-Guide.md for architecture, setup, run, env, proxy and Supabase configuration details.

## Build

pnpm build
