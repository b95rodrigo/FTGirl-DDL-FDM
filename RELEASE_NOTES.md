# FTGirl DDL FDM v1.1.2

Windows dependency installer hotfix; upstream **fitgirl-ddl-ng v0.4.14** remains unchanged.

## Fixes

- Avoid the shared pip cache (`--no-cache-dir`) to prevent `WinError 5: Access denied` during grapheme wheel creation.
- Improve pip diagnostics and output decoding.
- Add regression tests and Windows dependency-install validation.
- Preserve the existing installed dependency directory, pinned packages, FDM UUID and integration behavior.

## Release assets

- `FTGirl-DDL-FDM-v1.1.2.fda`
- `FTGirl-DDL-FDM-v1.1.2-source.zip`

Install over the existing add-on and restart FDM. Real-world Windows/FDM validation remains necessary.
