# Releasing the companion

The public repository is https://github.com/TamingYourAI/machines-that-answer-bookcode. Its
first commit is release 0.3.1, tagged `v0.3.1`: the release the book's Appendix O describes, so a
reader can check out exactly what the book names. Release 0.3.2, tagged `v0.3.2`, adds the
voice-agent test suite and loop detection. Each release is a source export of this folder, made
by the script below, and committed as one commit.

## Source-only export

From this root:

```sh
python scripts/export_release.py
```

The ZIP in `dist/` contains code, chapter fixtures, expected output, documentation, selected
synthetic validation records, license and CI. It excludes environments, downloaded models,
runtime data, credentials, test audio, generated build artifacts and the manuscript. Its
explicit file selection preserves the synthetic policy fixture needed by the app.

Extract it and use `open-voice-agents/` as the repository root; the book prints the public
repository's address. Apache-2.0 is the already approved code license. Review third-party model
terms separately; no weights are included. Design notes in `docs/specs/` stay out of the export.

## Provenance and divergence

[source-snapshot.json](source-snapshot.json) records original source hashes, the initial
authoring commit and inclusion of then-uncommitted work. Its `labs` entry records the book
commit the labs were last synced from with `python scripts/sync_labs.py` (run beside the
authoring project), which replaces every chapter folder and its hashes. The hashes
are provenance of the input, not final-release checksums. [changes](changes.md) describes
subsequent implementation fixes.

The full application is an independent release copy. Do not automatically overwrite it
from the author's `repo/`: that would discard the release fixes. Port reviewed changes
between the two trees deliberately. `python scripts/check_source_drift.py` detects changes
to the original chapter inputs while this folder is still inside the authoring project.
Published standalone clones use the saved snapshot instead.

## Dependencies and installation

`full-app/requirements.lock` pins the resolved dependency set for all application extras,
including local speech, for Python 3.12. Install it as **constraints** with `-c` so only
the selected extras are installed. It was generated with:

```sh
uv pip compile full-app/pyproject.toml --extra all --extra local --universal -o full-app/requirements.lock
```

macOS arm64 / Python 3.12 was executed locally. Linux Python 3.12 checks are configured
in GitHub Actions but have not run on GitHub. Build/test tools such as `build` and Playwright
are separate from runtime dependencies. The model setup records downloaded file hashes;
it is not a cryptographic attestation of an upstream model publisher.

## Persistence and compatibility

The operation schema gains a proposal fingerprint. Existing SQLite databases get the
column automatically, but legacy rows lack a trusted fingerprint and cannot replay as
authorized actions. Begin demonstrations with a new `OVA_DATA_DIR`. Do not infer support
for production database migration from this additive demo migration.

Same-ID retries are serialized within one ledger instance. Multiple workers, external
systems of record, and authenticated session recovery need additional design. Keep one
server process for the delivered application. See [delivery](delivery.md).

## Checks before publication

The [validation commands](validation.md) check the chapter export, application, package
and browser. Review the source archive contents before publishing. Live carrier and human
listening evidence can be added later without relabeling simulations as field evidence.
The generated source archive is ready to review; publication is a separate action.
