# Changelog

All notable changes to FTGirl DDL FDM are documented in this file.

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
