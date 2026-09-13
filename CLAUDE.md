# mrev — MusicXML Score Reverser

Converts MusicXML (`.mxl` / `.xml` / `.musicxml`) into a score that plays backwards.
See `README.md` for the reversal rules and usage.

## Commands

- Run: `python reverse_score.py` (reads `work/inbox/`, writes `work/outbox/<name>_rev.<ext>`); `-s` skips only broken measure contents
- Test: `python -m pytest tests/`
- Single test: `python -m pytest tests/test_key_time_scope.py -k <name>`
- IMPORTANT: always pass `tests/`. Bare `pytest` also collects the legacy root-level `test_*.py` scripts, and `test_viola_roundtrip.py` fails at collection.
- No `uv` / `npm` in this project; use plain `python`.

## Architecture

`process_file()` in `reverse_score.py` runs a multi-phase pipeline:

1. `layout_preservation.extract_layout_from_xml` reads the **original raw XML** before music21 touches it
2. music21 parses and reverses the score (`reverse_score` / `reverse_part`), then writes it
3. Raw-XML post-processing on the output file (`layout_preservation.py`): restore directions, normalize slurs, recalculate accidentals, re-place measure styles, strip horizontal layout hints
4. Apply transformed layout (`apply_layout_to_xml`) and restore print layouts lost in merged staves

Gotchas:

- music21's round-trip drops, splits, or invents elements. Decide behavior from attributes in the original XML, not from the presence of a music21 object.
- When restoring an element from the original, first remove what music21 wrote at the same spot (mixed id schemes create invalid references).
- Before writing a reversal formula, classify the marking as a **range** (valid until the next one), a **boundary** (switches at a point), or a **forward span** (e.g. `multiple-rest`). Most past bugs came from mixing these up.
- Horizontal positions (`default-x`, `<measure width>`) are invalid after reversal and are stripped on purpose; vertical layout is kept.

## Data and temp files

- `work/` is gitignored because scores are copyrighted. Real test scores live in `work/inbox/`; tests that need them `pytest.skip` when absent, so skips are expected.
- Put scratch files under `work/temp/`.

## Verifying changes

- Run `python -m pytest tests/` and report the pass/skip counts.
- For reversal-logic changes, also reverse a real score from `work/inbox/` and inspect the output XML at the affected measures.
- When a change normalizes or removes output, compare element counts between input and output across all files in `work/inbox/` and justify every decrease.
- Do not trust expected values in issues or user suggestions blindly; recompute them as intervals and cross-check against independent evidence (e.g. note positions).

## Language

Write commit messages, PR titles/bodies, issues, `README.md`, `tasks/*.md`, code comments, and test docstrings in **Japanese**.

## Git workflow

- Branch from `master` as `type/<issue>-description` (e.g. `fix/88-unclear-end-arrow`).
- Conventional Commits, one logical change per commit (e.g. `fix: ...`, `docs: ...`).
- PR title ends with `(Closes #<issue>)`; run the test suite before opening the PR.
- If a change affects reversal behavior, CLI options, or output, update `README.md` in the same PR.

## Task notes (`tasks/`)

- `tasks/todo.md`: for each issue, add a `## Issue #N: ...` section with a checklist, then a review and verification section when done.
- `tasks/lessons.md`: read the relevant entries before working on reversal logic. After the user corrects you, add the pattern as a rule.
