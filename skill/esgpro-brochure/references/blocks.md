# Block catalogue

Every standard page is `{"kicker", "title", "title_em", "subtitle", "blocks": [...]}`. Blocks stack top to bottom with measured heights; the build fails if they overflow the page. `*` marks an infographic block (each page needs at least one).

| Block | Use it for | Key fields |
|---|---|---|
| `kpi_row`* | 2–4 headline numbers | `items[{value,label,note?,icon?}]`, `variant: dark` |
| `stat_band`* | One big number with its meaning | `value, title, text, value_width, variant` |
| `process_flow`* | 3–6 sequential phases (chevrons) | `steps[{title,text,output?}]`, `from`, `to` colours |
| `week_plan`* | Gantt of workstreams across weeks/months | `columns[]`, `rows[{label,bars[{start,end,title,text?,milestone?}]}]` |
| `timeline`* | Week/module detail, vertical rail | `items[{tag,meta,title,points[] or text,output?,highlight?}]`, `gap` |
| `module_grid`* | 4–8 modules as cards | `modules[{code,title,meta?,points[],output?}]`, `columns` |
| `icon_grid`* | Drivers, features, support resources | `items[{icon,title,text}]`, `columns`, `layout: side/top`, `boxed` |
| `comparison`* | Alternatives vs this programme; standards x weeks | `columns[]`, `rows[{label,values[true/false/"text"]}]`, `highlight` |
| `evidence_table`* | Numbered deliverables + why each matters | `rows[{title,text,why,icon}]`, `left_header`, `right_header` |
| `ladder`* | Capability or career progression | `steps[{level,title,text}]`, `base`, `step` |
| `bar_chart`* | Sourced quantitative comparison | `items[{label,value,display?,highlight?}]`, `title`, `source` (required in practice) |
| `donut`* | Share of time/effort/credits | `segments[{label,value,display}]`, `centre`, `centre_label` |
| `matrix_2x2`* | Positioning frameworks | `quadrants[4]{title,text,highlight?}`, `x_axis`, `y_axis` |
| `mentor`* | Faculty profile (photo, bio, credentials, stats) | `person` (id in facts.json) |
| `testimonials`* | Alumni proof cards | `ids[]` (facts.json testimonials) |
| `pricing`* | Fee cards | `options[{label,price,note,features[],highlight?,tag?}]` |
| `cta` | Closing call to action with QR | `title,text,steps[],button,url,url_text,qr_url,contact` |
| `callout` | A single key message | `title,text,icon,variant: dark/soft/gold` |
| `pull_quote` | Memorable line from the programme's thesis | `text, attribution` |
| `checklist` | Inclusions, criteria | `items[]`, `columns`, `title` |
| `text_list` | FAQs, terms, who-for | `items[{title,text}]`, `columns` |
| `split` | Two stacks side by side | `ratio`, `left[]`, `right[]`, `valign` |
| `logo_strip` | Client/partner logos (with permission) | `ids[]` (manifest, role `partner_logo`) |
| `label`, `paragraph`, `divider`, `spacer` | Structure | — |

Cover template fields: `kicker, title, title_em, subtitle, lead, band_label, kpis[4], band_statement, workflow[4], quick_facts[4], disclaimer`. The mentor on the cover uses `people.mentor.cover_photo`.

Icons available: `bolt book briefcase building bulb calendar certificate chart check clock cloud co2 coins cycle document factory flag gear globe layers leaf mail medal mic network people route scale search shield target trend truck`.

## Example: pathway page

```json
{
  "kicker": "02 / The pathway",
  "title": "Four weeks. Four phases.",
  "title_em": "One defensible file.",
  "subtitle": "Each week ends in something you have built and submitted.",
  "blocks": [
    {"type": "process_flow", "steps": [
      {"title": "MEASURE", "text": "Boundary, Scope 1 and 2.", "output": "Scope 1 & 2 inventory"},
      {"title": "EXTEND", "text": "Scope 3 screening.", "output": "Scope 3 calculation"},
      {"title": "DEFEND", "text": "Audit a defective file.", "output": "Marked findings"},
      {"title": "REDUCE", "text": "SBTi targets.", "output": "Target file"}]},
    {"type": "split", "ratio": 0.46, "valign": "center",
     "left": [{"type": "donut", "centre": "4", "centre_label": "weeks", "segments": [
        {"label": "Measure", "value": 2, "display": "50%"},
        {"label": "Defend", "value": 1, "display": "25%"},
        {"label": "Reduce", "value": 1, "display": "25%"}]}],
     "right": [{"type": "callout", "title": "Measuring is half the job.", "text": "..."}]}
  ]
}
```
