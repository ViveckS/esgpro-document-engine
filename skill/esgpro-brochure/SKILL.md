---
name: esgpro-brochure
description: Create or update ESGPro Mastery Institute programme brochures (PDF) with the esgpro-document-engine brochure builder. Use for any new programme brochure, a refreshed edition (e.g. v2027), a fee or cohort update, or a request to make a brochure "more visual", "consulting-style", or "consistent with CCMP". Always runs the intake questions first; never drafts a brochure from memory.
---

# ESGPro brochure skill

You produce programme brochures that look like one family: same theme, same component library, same shared facts, one unique photo per person. Every consistency rule below is enforced by `brochure.py`; your job is to supply correct content and a strong page plan.

## 0. Setup

```bash
pip install -r requirements.txt            # reportlab, Pillow (+ pymupdf for previews)
ls private_assets/                         # facts.json, manifest.json, logos/, people/, programmes/
```

If `private_assets/` is missing, stop and ask the owner for it (it is git-ignored on purpose: logos, portraits, testimonials).

## 1. Intake: ask before you draft (mandatory)

For a **new** programme:

```bash
python brochure.py new <programme-id>                # copies programmes/_template.json
mv programmes/<programme-id>.json private_assets/programmes/
python brochure.py intake private_assets/programmes/<programme-id>.json
```

Ask the user every open question the intake prints, grouped (Identity, Audience, Format, Curriculum, Fees, Enrolment, Proof, Assets, Guarantees). Ask in one message, numbered, with the example answer shown so they can reply quickly. Do not fill gaps with plausible guesses. If an answer is unknown, use the approved wording they give (e.g. "Next cohort: confirm with admissions"), never TBC.

For an **update** of an existing brochure, still ask:
1. Have any shared facts changed? (participants trained, company transformations, mentor bio, client names)
2. What changed in fees, dates, curriculum or enrolment URL?
3. Which testimonials should appear, and are there new photos?

Always confirm the enrolment URL by asking whether it is the live page; flag URLs containing `copy`, `draft`, `test` or `example.com`.

## 2. Facts live in one place

- Shared numbers and people come from `private_assets/facts.json`. Reference them as `{{fact.participants_trained}}`, `{{fact.company_transformations}}`, `{{contact.phone}}`, etc. **Never type a shared number into a programme file.**
- When the owner gives a new figure, update `facts.json` and move the old value to `retired_values`; the build then fails anywhere the old figure survives.
- Programme-specific values (fee, duration, cohort size, URL) go in the programme file's `vars` and are referenced as `{{var.*}}`.
- No invented statistics, market sizes, salary claims, outcomes or client names. Every claim must trace to the owner, a prior approved brochure, or a cited public source. Testimonials: only the fields in `facts.json`; do not write outcomes for people who did not give one.

Current owner-confirmed headline facts (2026-09-28): **10,500+ participants trained; 100+ company transformations.**

## 3. Page architecture (8 pages, consulting style)

Each page makes one argument. The **action title** states the takeaway (Caladea, max 2 lines; second line in `title_em` italic). The subtitle gives the evidence. Every page carries at least one infographic block; the same infographic type on more than two pages triggers a warning.

| # | Page | Job | Default blocks |
|---|------|-----|----------------|
| 1 | Cover | Name, promise, proof | `cover` template: title/title_em, KPI tiles from facts, circular mentor portrait, 4-step workflow chips, quick facts |
| 2 | Why now | The market problem | `icon_grid` (6 drivers) + `comparison` (alternatives vs this programme) + `pull_quote` |
| 3 | The pathway | How it works end to end | `process_flow` (phases + outputs) + `week_plan` (Gantt) + `split`(`donut`, `callout`) |
| 4 | Curriculum | What is taught | `timeline` (week/module, 3 points + "Builds") + `comparison` (standards x weeks) |
| 5 | Deliverables | What they walk out with | `evidence_table` + `process_flow` (build/submit/marked/fix) + `stat_band` + `checklist` |
| 6 | Method | Why this works | `ladder` (capability levels) + `icon_grid` (what each week contains) + `split` of two `callout`s (for / not for) |
| 7 | Faculty and proof | Trust | `mentor` (office portrait) + `testimonials` (outcomes) + `testimonials` (alumni with photos) + caption disclaimer |
| 8 | Investment | Decision | `pricing` (highlight one card) + `text_list` (guarantee, teams, students) + `cta` (steps, button, QR) |

Adapt the plan to the programme (a 6-month programme may use `module_grid` and a 6-column `week_plan`), but keep cover, proof and investment pages, and keep one message per page.

Block catalogue with JSON examples: `references/blocks.md`. Writing rules: `references/writing.md`.

## 4. Images: no repeats, no gaps

- Register every image in `private_assets/manifest.json` with a `role`.
- The mentor needs two different portraits: `cover_photo` (circle on the cover) and `photo` (profile page). Portraits default to one use each, so a repeat fails the build.
- Each testimonial with a photo must use its own image; near-duplicate photos under different ids fail the build. Testimonials without photos get initials avatars.
- A missing logo or mentor photo fails the build. Use `--allow-placeholders` only for early drafts shared internally.

## 5. Build, inspect, iterate

```bash
python brochure.py build private_assets/programmes/<id>.json --output output/<id>.proof.pdf --proof --previews
python brochure.py build private_assets/programmes/<id>.json --output "output/<Title> <edition>.pdf" --previews
python self_test.py
```

Then **look at every page preview** (`output/<name>_previews/page_NN.png`). Fix, rebuild, re-inspect. The build blocks on: overflow, unresolved tokens, retired or conflicting facts, TBC/TODO/example.com, missing or repeated images, theme overrides, pages without an infographic, and titles over two lines. Warnings flag large empty areas and repeated infographic types; resolve them too.

## 6. QA checklist before you hand over

- [ ] Intake questions answered by the owner; no guessed facts
- [ ] Headline facts match `facts.json`; no retired values anywhere
- [ ] Cover shows the mentor portrait; profile page uses the second portrait
- [ ] Every testimonial photo unique and permitted; alumni names/roles as supplied
- [ ] Every page: action title, subtitle, at least one infographic, no large empty area
- [ ] Palette and page backgrounds untouched (theme-locked)
- [ ] Fees, booking/balance maths and currency correct; enrolment URL opened and confirmed live
- [ ] QR decodes to the enrolment URL; links clickable
- [ ] Disclaimers present: institute-reported figures, outcomes not guaranteed, permissions
- [ ] Clean PDF and proof PDF delivered; list of open questions for the owner

## 7. Files

```
brochure.py            builder CLI (build / intake / new)
brochure_icons.py      vector icon set (24-unit grid)
themes/esgpro.json     locked CCMP palette, type scale, layout, design rules
intake/questions.json  intake questionnaire
programmes/_template.json   8-page structure with TODO slots
programmes/demo.json   neutral demo (builds without private assets)
private_assets/        facts, images, real programme files (git-ignored)
```
