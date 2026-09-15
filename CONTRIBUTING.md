# Contributing

## Repository workflow

The project's writable remote is `origin`, pointing to
`https://github.com/jstncg/melee-macos-recomp.git`. The original project is retained
as `upstream`. After the required checks pass, commit relevant source changes and
push the working branch to `origin` unless the user asks to keep that work local.
Verify the remote commit matches the local commit after pushing.

## Source and verification

Keep changes in this repository's source files and reproducible patches. Do not
commit downloaded upstream trees, game images, extracted assets, generated game
code, compiled game modules, saves, screenshots of game content, or credentials.
Use a locally supplied compatible disc for integration tests. Do not ask for or
provide game downloads in issues or pull requests.

Run the synthetic tests and release audit before committing. For runtime patches,
verify that they apply to the pinned revisions and report the relevant local
integration test. Be precise about what was actually tested; in particular, local
netplay boot is not evidence of a completed internet match.

Include macOS version, hardware, commit, reproduction steps, and a minimal relevant
log excerpt in bug reports. Remove personal paths and never attach game data.
