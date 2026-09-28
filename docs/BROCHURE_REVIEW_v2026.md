# Review: why the v2026 brochures drifted from CCMP 2.0

Compared: `CCMP_Brochure_2.0.pdf` (the original), `GHG & SBTi Net-Zero Practitioner Programme v2026.pdf` and `Advanced Certificate in GHG & Net-Zero Practitioner Programme v2026.pdf`, the last two produced through the six-page slot layout (`layouts/six_page.json`).

## What went wrong, and the root cause of each

| Symptom in the v2026 output | Root cause in the engine or skill | Fix in v2 builder |
|---|---|---|
| No mentor photo on the SBTi cover; the Advanced Certificate repeated the same portrait on pages 1 and 2 | Image slots were optional and unregistered. The same file could fill any slot any number of times, and an empty slot rendered silently as blank | Image manifest with roles. A missing mentor/logo photo blocks the build. Portraits are single-use by default, and near-duplicate photos under two names fail (perceptual hash) |
| Alumni cards without photos | Testimonial images were decoupled from the people they belong to | Testimonials live in `facts.json` with their own photo id; no photo means an initials avatar, never an empty box |
| Page backgrounds and greens changed (#1D3328 and #D4A849 vs CCMP #1A5D49 and #C3A746), and page 2's panel colour differed between files | Colours were per-element in each layout copy, so every new brochure could re-colour anything | One locked theme (`themes/esgpro.json`) using the CCMP palette. Programme files cannot set colours or backgrounds (build error) |
| Conflicting facts: 4,600+ (CCMP), 6,900+ (Advanced), 10,500+ and 7,000+ (SBTi); "100+ organisations advised" | Every brochure retyped its numbers into free-text slots. Numeric locks only froze whatever was typed first | Single `facts.json`; programmes use `{{fact.*}}` tokens. Superseded values are listed as `retired_values` and fail the build; regex guards catch "N participants trained" that disagrees with the fact |
| "–" placeholders instead of numbers in the page-1 at-a-glance tiles | Slot geometry was inherited from CCMP ("01/02/03" workflow tiles) and repurposed for other content, with filler for the unused slot | Cover is a component: KPI tiles take values from facts; nothing is inherited from another programme's geometry |
| All links in both files pointed to `https://example.com` | Skeleton link placeholders were never replaced, and `example.com` passed the URL syntax check | `example.com`, TBC, TBD and TODO are build errors. The QR is generated from the same enrolment URL variable as the button |
| The Advanced Certificate QR opens a course URL containing `-Copy-` | No check that the enrolment destination is the live page | Intake asks the owner to confirm the live URL. The skill flags `copy/draft/test` URLs |
| Pages read as text blocks; few infographics | The slot layout only had rectangles, lines, text and images, and each page was a CCMP clone | 27 block types (process flow, Gantt week plan, timeline, comparison matrix, evidence table, ladder, donut, bar chart, 2x2, KPI tiles, pricing, CTA with QR) plus a vector icon set. Every page must contain an infographic; repeated infographic types are flagged |
| Logo differed from CCMP (a retyped "ESGPro / Mastery Institute" wordmark) | No logo registry | The manifest registers one approved lockup (the CCMP 4480px logo with tagline) |
| New programmes started without asking for facts | The skeleton was 180 empty slots with no questions | `brochure.py intake` prints the unanswered questionnaire; the skill must ask these before drafting |

## Design upgrades (consulting style)

- Action titles on every page: a serif statement with an italic turn ("Everyone can define Scope 3. *Few can defend it.*").
- One message per page with the evidence as an infographic, in pyramid order: title, subtitle, visual, caveat.
- Eight pages: cover, why now, pathway, curriculum, deliverables, method, faculty and proof, investment.
- The cover keeps CCMP's DNA (light title zone, forest proof band, mentor portrait, workflow chips, quick facts) but now shows owner-confirmed proof: 10,500+ participants trained and 100+ company transformations.

## Open items for the owner

1. The Advanced Certificate QR and link go to a learn.esgpro.in course URL containing `-Copy-`. Confirm it is the live page.
2. The mentor name is "Viveck J Suman, CFA" in CCMP and "Viveck Jai Suman, CFA" in the v2026 drafts. The facts file uses the latter.
3. "7,000+ professionals through long-format programmes" is retired pending confirmation.
4. The standards-by-week matrix (curriculum page) is an editorial mapping of the published curriculum. Please confirm it.
5. Next cohort start dates are not stated; the brochures say "confirm with admissions".
