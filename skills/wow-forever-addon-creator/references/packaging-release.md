# Packaging and release

## Zip layout

```
MyAddon-1.2.0.zip
└── MyAddon/            ← exactly the TOC name; the client ignores mismatched folders
    ├── MyAddon.toc
    ├── Core.lua ...
    ├── Media/
    └── LICENSE.txt
```

- Exclude dev files: `.luacheckrc`, tests, `*.tmp`, files starting with `_`, source art.
- Every file listed in the TOC must be in the zip, and nothing the TOC needs may be missing.
- Write entries in sorted order with a fixed timestamp (`zipfile.ZipInfo(name, date_time=(2026,1,1,0,0,0))`) so rebuilding the same source gives the same SHA-256.
- Normalise line endings before packaging (a CRLF checkout changed a zip by 91 bytes and broke SHA comparison).
- After writing: reopen the zip, run `testzip()`, compare the name list and each file's bytes with the source, check TOC Title/Version/SavedVariables.
- Publish the SHA-256 and size next to the download; verify the live download matches.

## Versions and metadata

- `## Version:` read at runtime with `C_AddOns.GetAddOnMetadata(addonName, "Version")`.
- Optional `## X-Website:`, `## IconTexture:`; colour codes are allowed in `## Title:`.
- Strip upstream `## X-Curse-Project-ID` / `## X-Wago-ID` when you redistribute a fork under your own name.

## Languages

Two workable models:
1. One package with a locale table chosen by `GetLocale()`.
2. One package per language with a one-line `Dil.lua`/`Lang.lua` written by the packager (`ns.PACKAGE_LANG = "tr"`), plus a single-copy guard so installing both runs only one.

Model 2 suits audiences that play an English client but want a translated UI.

## Licences

- Own code: state a licence explicitly (MIT, GPL, or "all rights reserved, free to share unchanged").
- Derivatives of GPL addons are GPL: ship the licence and a NOTICE of changes.
- Third-party art and fonts: keep a licences table; bundle OFL texts with fonts.
- Do not ship Blizzard game files or extracted assets; reference them by path or FileDataID.
- Add a trademark disclaimer (not affiliated with Blizzard Entertainment).

## Release checklist

1. All offline gates PASS, negative run all red.
2. In-game test notes written: what was seen, what was not tested.
3. Version bumped in TOC and changelog.
4. Zip built reproducibly, reopened and compared, SHA recorded.
5. After upload: download the live file and compare SHA.
