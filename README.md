# ESGPro Document Engine

A reusable Python PDF publishing engine with premium serif typography, structured content and explicit publication checks. Code and templates are MIT licensed; see [NOTICE.md](NOTICE.md) for font and brand boundaries.

It has two renderers:

- **`brochure.py`, the brochure builder (v2, recommended).** Pages are composed from 27 infographic blocks under one locked theme. Shared facts, people and photos come from single registries, and the build fails on drift: stale numbers, repeated or missing photos, colour overrides, overflow, placeholder links, or pages without an infographic.
- **`render.py`, the fixed-slot renderer (v1).** Coordinate-level layouts with approval hashes. It is kept for existing documents.

## Quick start

Python 3.10 or newer:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python brochure.py build programmes/demo.json --output output/demo-brochure.pdf
python self_test.py
```

Optional: `pip install pymupdf` and add `--previews` to write PNG previews of each page.

## Create a programme brochure (v2)

```bash
python brochure.py new my-programme                 # copies programmes/_template.json
python brochure.py intake programmes/my-programme.json   # the questions to answer first
python brochure.py validate programmes/my-programme.json # validate facts, tokens, assets without writing PDF
python brochure.py build programmes/my-programme.json --output output/review.pdf --proof --previews
python brochure.py build programmes/my-programme.json --output "output/My Programme v2026.pdf" --previews
```

- **Facts:** shared numbers and people live in a facts file (`facts/demo_facts.json` for the demo; your real one in git-ignored `private_assets/facts.json`). Programme files reference them as `{{fact.*}}`, and superseded values go in `retired_values` so they can never reappear.
- **Images:** every image is registered in a manifest with a role. Portraits are single-use, near-duplicates are detected, and a missing mentor photo or logo blocks the build.
- **Theme:** `themes/esgpro.json` locks the palette, type scale and page backgrounds.
- **Page plan and writing rules:** see the skill in [`skill/esgpro-brochure/`](skill/esgpro-brochure/SKILL.md) and [docs/BROCHURE_REVIEW_v2026.md](docs/BROCHURE_REVIEW_v2026.md) for why these gates exist.

## Skill (Claude and ChatGPT)

`skill/esgpro-brochure/SKILL.md` is the single source of truth. It covers the mandatory intake questions, the 8-page consulting-style architecture, the block catalogue and a QA checklist. Package it with:

```bash
python tools/package_skill.py                  # public engine + skill -> dist/esgpro-brochure-skill.zip
python tools/package_skill.py --with-private   # adds private_assets/ for the owner's own upload only
```

Upload the zip as a Claude skill or to the ChatGPT `esgpro-publish` skill. Uploaded skills are snapshots, so re-package after changes.

## Fixed-slot renderer (v1)

### Create another document

1. Copy `models/demo_content.json` and `layouts/demo.json`, or start from `models/new_programme_skeleton.json` paired with `layouts/six_page.json`.
2. Edit `brand_config.json` and replace the demo wordmark with your authorised logo. Asset paths resolve relative to `render.py`.
3. Fill every text slot, retain evidence and review numerical tokens explicitly. The six-page skeleton intentionally refuses to export until filled. Its image slots and example.com links must be replaced.
4. Render using explicit paths, then inspect every page:

```bash
python render.py --content models/my_content.json --layout layouts/my_layout.json --config brand_config.json --output output/review.pdf
python render.py --content models/my_content.json --layout layouts/my_layout.json --hashes
```

5. Resolve `open_issue_ids`, review claims and provenance, record named approval/date, visual and link checks, and copy current hashes into the approval fields. Set configuration approval to `approved_by_owner` only following actual approval. Run the same command with `--final`.

The supplied demo intentionally fails final export. See [docs/RELEASE.md](docs/RELEASE.md).

## Capabilities and limits

- Content, styles and geometry are separate JSON files.
- Fixed-slot text measurement, missing-font/asset checks, numerical-change detection and approval hashes.
- Vector primitives in `render.py` include rect, line, circle, badge, text, label, image, wave, and link.
- Runtime JSON Schema validation via `content.schema.json` and `jsonschema` (CLI `--validate-schema`).
- Automatic PNG page previews via PyMuPDF / pdftoppm (`--previews`).
- Fast preflight validation CLI for brochures (`brochure.py validate`).
- Any number of declarative pages; no automatic pagination, content writing or fact verification.
- Human visual QA remains necessary: the renderer does not detect every overlap or inspect every non-text boundary.
- Output is RGB PDF with selectable text and embedded fonts, not PDF/X or certified press-ready output.
- Only process trusted local models and assets. This is a desktop publishing tool, not a hardened multi-user service.

## Contributing

Keep changes focused and run `python self_test.py` plus both demo renders. Inspect affected pages when layouts or blocks change. Include rights information for any added assets. Never commit secrets, client documents, portraits, testimonials or unsupported programme claims; those belong in `private_assets/`.
