# Changelog

All notable changes to FTGirl DDL FDM are documented in this file.

## [1.1.3] - 2026-11-24

### Fixed

- Keep PrivateBin list parsing local; do not launch a browser on API or decryption failure.
- Preserve the underlying failure message, retry transient HTTP errors, support compressed JSON responses and avoid logging the paste key in the batch parser.
- Prevent browser cleanup errors from masking real results or failures in other flows.
- Add regression tests for multi-file lists, API errors and browser cleanup; validate an encrypted synthetic playlist in Windows CI.

## [1.1.2] - 2026-11-24

### Fixed

- Disable pip's shared cache during dependency installation to avoid Windows `WinError 5` when building the grapheme wheel for Zendriver.
- Decode pip output as UTF-8 with replacement and retain more diagnostic details.
- Add regression tests for cache-free installation and reuse of existing dependencies, plus a Windows dependency-install smoke test with an unusable cache path.
- Keep upstream 0.4.14, dependency versions and FDM UUID unchanged.

## [1.1.1] - 2026-11-24

### Upstream sync

- Track upstream **0.4.14** (commit `8dbe0984`, released 2026-11-08).
- Accept anchors nested inside spoiler content, including paragraphs, following upstream selector fix `120eedc0`.
- Add regression coverage for nested anchors, ordering, duplicates and unsupported hosts.
- Keep Python 3.11+, Zendriver 0.17.1 and the existing dependency cache; no new runtime dependencies.
- Preserve FDM playlist behavior, UUID, on-demand resolution and local PrivateBin support. Upstream GUI-only exception handling and telemetry changes are not applicable to this add-on.

## [1.1.0] - 2026-10-09

### Upstream sync

- Adapted parser behavior to `mokurin000/fitgirl-ddl-ng` **0.4.12** (upstream commit `7fc99c35`).
- Bumped runtime compatibility to Python 3.11+ and Zendriver 0.17.1.
- Adopted the current `POST /f/{id}/go` HTMX response contract and added resilient browser retries/backoff.
- Updated FitGirl spoiler link collection to match upstream page selectors.
- Added PrivateBin HTTP-to-browser fallback and stricter supported-host validation.
- Preserved on-demand link resolution and FDM playlist selection.
- Added Python unit tests, PR validation workflow and upstream MIT attribution.

## [1.0.0] - 2026-09-20

### Added

- First stable release under the **FTGirl DDL FDM** project name.
- FDM playlist integration for `paste.fitgirl-repacks.site` FuckingFast mirrors.
- Local PrivateBin AES-GCM decryption with PrivateBin-compatible raw DEFLATE handling.
- Per-file FuckingFast direct-link resolution when each selected download starts.
- Support for individual FuckingFast links and FitGirl page fallback flows.
- English README as the primary documentation.
- Complete PT-BR documentation in `README.pt-BR.md`.
- Step-by-step FDM installation and usage guide.
- Reproducible Windows, Linux and macOS packaging scripts.

### Compatibility

- The legacy internal UUID `fitgirl-ddl-ng-fdm` is retained to preserve the upgrade path from development builds 0.1.x.
