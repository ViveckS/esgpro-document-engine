# ESGPro Document Engine

A reusable Python PDF renderer with premium serif typography, structured content models and explicit publication checks. Code and templates are MIT licensed; see [NOTICE.md](NOTICE.md) for font and brand boundaries.

## Quick start

Python 3.10 or newer:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python render.py
python self_test.py
```

Windows activation: `.venv\Scripts\activate`. The default command creates `output/demo.pdf` and `output/demo.qa.json`. The two-page neutral demonstration runs without private assets. Fonts are bundled with their original licences. No network access is needed after installing dependencies.

## Create another document

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
- Any number of declarative pages; no automatic pagination, content writing or fact verification.
- Human visual QA remains necessary: the renderer does not detect every overlap or inspect every non-text boundary.
- Output is RGB PDF with selectable text and embedded fonts, not PDF/X or certified press-ready output.
- `content.schema.json` is a reference contract; runtime does not currently execute JSON Schema validation.
- Only process trusted local models and assets. This is a desktop publishing tool, not a hardened multi-user service.

## Reuse in ChatGPT

The source repository is https://github.com/ViveckS/esgpro-document-engine.
For the owner's ChatGPT Work account, the installed `esgpro-publish` skill bundles the renderer and private brand configuration. Invoke it with: "Use esgpro-publish to create a brochure from this content."

The skill uses a saved snapshot; GitHub changes do not automatically update it. Other users can clone this repository and follow the quick start. This repository is a Python tool, not a hosted API or a GPT Action.

## Contributing

Keep changes focused and run `python self_test.py` plus the demo render. Inspect affected pages when layouts change. Include rights information for any added assets. Never add secrets, client documents or unsupported programme claims.
