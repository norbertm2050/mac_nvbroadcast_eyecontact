# Maintainer release checklist

1. Use a clean checkout and pinned Python dependencies on each platform. Never copy user config, keys, logs, private benchmarks or recorded camera frames into the checkout or bundle.
2. Run unit and platform hardware tests. Exercise real camera output, stop/start, restart, and disconnection recovery on both machines. Verify hardware acceleration in status files.
3. Collect third-party notices, run platform build scripts, and prepare the matching dependency source archive with `scripts/fetch-dependency-sources.py`.
4. Scan source, reachable Git history, extracted application archives and Python archive entries for private addresses, absolute user paths, credentials and debug data. Review the file list before publishing.
5. Create a version commit/tag only after tests and scans pass. Calculate SHA-256 checksums for the two application archives and the dependency source archive. Upload all assets together with matching source.
6. Do not describe unsigned/ad-hoc-signed bundles as Apple-notarized or Microsoft-signed. For a notarized release, use a maintainer-owned Developer ID and Apple notary credentials; do not embed them in Git or the application.

The Mac `.app` is relocatable as a whole. The Windows `.exe` is relocatable together with its sibling runtime files. No build-time checkout path is used by either program.
