# Generation Prompt Examples — Phase 05

## Purpose

Phase 04 creates `GENERATION_PROMPT.md`. This file defines the minimum useful prompt structure for Phase 05. The generator must receive verified facts, missing fields, forbidden claims, required sections, output requirements, and the fact usage report requirement. The `fact_usage_report.json` schema is defined in `docs/templates/site_template_spec.md`.

---

## Example 1 — Restaurant

```md
# Generate one-page preview website

## Goal
Create a fast, mobile-friendly one-page preview website for a local restaurant using only the verified facts below.

## Verified facts
- business_name: Mae Rim Garden Kitchen
- category: Thai restaurant
- rating: 4.6
- review_count: 128
- address: Mae Rim, Chiang Mai, Thailand
- phone: +66 53 000 000
- hours: Not listed
- maps_url: https://maps.google.com/example
- website_status: no_website

## Missing fields
- menu URL
- prices
- owner/staff names
- delivery options
- photos

## Required sections
1. hero
2. services/category overview
3. trust section using only rating/review count
4. location/hours
5. Google Maps link/embed
6. call CTA
7. footer

## Copy rules
- Use category-level restaurant copy only.
- Do not invent menu items, prices, delivery, awards, family ownership, or years in business.
- If hours are missing, say: `Hours not listed in source data`.
- If a field is missing, omit it or use neutral missing-data wording.

## Forbidden claims
Do not use: award-winning, best in town, authentic since, family-owned, trusted by thousands, guaranteed, certified, testimonials, menu prices, chef names.

## Output files
- site folder
- build_status.json
- fact_usage_report.json
- screenshot_desktop.png
- screenshot_mobile.png

## Fact usage report
Use the schema from `docs/templates/site_template_spec.md`. For every business-specific statement, write the source field and where it appears on the site. Flag any generic copy separately.
```

---

## Example 2 — Dentist / Clinic

```md
# Generate one-page preview website

## Goal
Create a clean, professional one-page preview website for a local dental clinic using only verified facts below.

## Verified facts
- business_name: Bright Smile Dental Clinic
- category: Dental clinic
- rating: 4.8
- review_count: 64
- address: Maplewood Road, Chiang Mai, Thailand
- phone: +66 81 000 0000
- hours: Monday-Friday 09:00-18:00
- maps_url: https://maps.google.com/example
- website_status: social_only

## Missing fields
- dentist names
- exact treatment list
- license/certification details
- prices
- emergency availability
- insurance/payment options

## Required sections
1. hero
2. services/category overview
3. trust section using only rating/review count
4. location/hours
5. Google Maps link/embed
6. call CTA
7. footer

## Copy rules
- Use only generic dental-clinic category copy.
- Do not list treatments unless explicitly verified.
- Do not claim licensed, certified, emergency care, painless care, specialist care, or guaranteed outcomes.
- Do not invent staff names or credentials.

## Forbidden claims
Do not use: licensed dentists, certified specialists, emergency care, painless treatment, best clinic, award-winning, years of experience, testimonials, prices, guarantees.

## Output files
- site folder
- build_status.json
- fact_usage_report.json
- screenshot_desktop.png
- screenshot_mobile.png

## Fact usage report
Every factual statement must map to a verified fact. If a claim cannot be mapped, remove it before final output.
```
