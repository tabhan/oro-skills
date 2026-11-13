# Asset-version cache busting after a build

## 10. Asset-version cache busting after a build

After rebuilding webpack assets (`oro:assets:build` + `assets:install --symlink`), the
`?v=<hash>` in `public/build/build_version.txt` does **not** change automatically. Browsers keep
the old `app.js` under the stale `?v=`, and an SRI integrity mismatch then **blocks** the script
(`Failed to find a valid digest in the 'integrity' attribute` → `ReferenceError: loadModules is
not defined`). Fix: run `composer run set-assets-version` to bump the version so every asset URL
refetches with a consistent integrity hash. Separately, a native nginx `open_file_cache` can
serve stale precompressed bytes right after a build (transient SRI mismatch) — the version bump
is the durable cure.

