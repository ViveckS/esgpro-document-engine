# Private assets (git-ignored)

This repository is public, so organisation-specific material stays out of git. Everything in this folder except this README and `manifest.example.json` is ignored.

Expected layout for the ESGPro brochures:

```
private_assets/
  manifest.json          # image registry (copy manifest.example.json)
  facts.json             # shared facts, people, testimonials, retired values
  logos/                 # approved logo lockups
  people/                # mentor portraits, one unique photo per alumnus
  programmes/<id>.json   # programme files for real brochures
```

Rules the builder enforces:

- Every image is registered once, with a `role` (`logo`, `portrait`, `photo`, `partner_logo`).
- A portrait or photo appears at most once per brochure unless `max_uses` says otherwise. Register a second portrait (e.g. `mentor_studio` for the cover, `mentor_office` for the profile) instead of repeating one.
- Two ids pointing at the same or near-identical photo fail the build.
- A missing mentor photo, logo or testimonial photo fails the build. `--allow-placeholders` draws a loud "PHOTO NEEDED" box for drafts only.
- Only add images you have rights to use. Record the `source` of each.

To use the skill on another machine, copy this folder alongside the repository or run `python tools/package_skill.py --with-private` to bundle it into your own (not shared) skill upload.
