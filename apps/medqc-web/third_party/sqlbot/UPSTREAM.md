# SQLBot Upstream Snapshot

## Source

- Upstream repository: https://github.com/dataease/SQLBot
- Branch: `main`
- Commit SHA: `2e4f3bf98c141974616789a62dff9c06b92b7c64`
- Snapshot date: `2026-06-07`

## Copy Policy

This directory is a vendored third-party source snapshot. It is kept outside the
main `src/` and `backend/app/` application trees and must not be mixed into the
MedQC build pipeline by default.

The snapshot was copied without these local or generated artifacts:

- `.git/`
- `node_modules/`
- `dist/`
- `target/`
- `build/`
- `.gradle/`
- logs and temporary files
- local environment files such as `.env` and `.env.*`

## License And Branding

SQLBot is distributed under its upstream license. Keep the original `LICENSE`,
README, copyright notices, logo, and branding information when updating this
snapshot or building a derivative deployment.

Before shipping SQLBot together with MedQC, confirm the distribution obligations
for the SQLBot license and any transitive dependencies.
