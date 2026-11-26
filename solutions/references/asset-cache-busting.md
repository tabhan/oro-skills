# Asset-version cache busting after a build

After `oro:assets:build` + `assets:install --symlink`, the `?v=<hash>` in `public/build/build_version.txt` does not
change. Browsers keep the old `app.js` under the stale `?v=`, and the SRI integrity mismatch **blocks** the script
(`Failed to find a valid digest in the 'integrity' attribute` -> `ReferenceError: loadModules is not defined`).

Fix: `composer run set-assets-version`. This is the durable cure; nginx `open_file_cache` can also serve stale
precompressed bytes right after a build (transient SRI mismatch).
