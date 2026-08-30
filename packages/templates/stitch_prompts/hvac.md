# Stitch Prompt Template: HVAC

Facts-only policy: this prompt contains structure, layout, and tone guidance only.
Every business fact must come from a {{verified_field}} placeholder supplied with the
prompt. If a verified field is absent, instruct the model to omit that element -
never to invent a default value. Never display a `$` amount unless it comes from a
verified field.

Design a premium single-page business website for {{business_name}}, an HVAC service in {{city}}.

## Layout Structure

1. **HERO section**: headline focused on the verified service offering, "Serving {{city}} since {{years}}" (only if {{years}} is verified; otherwise omit), phone CTA "Call: {{phone}}"
2. **SERVICES grid**: one card per verified service from the brief, with name and description only - do not display prices unless a verified price is supplied
3. **TRUST section**: {{rating}} stars from {{review_count}} reviews (only if both are verified; otherwise omit the rating block entirely)
4. **LOCATION**: Service {{city}} and surrounding areas, map embed, verified hours of operation (omit the hours block if none are verified)
5. **CTA**: "Schedule your service - {{phone}} or online booking" (omit any channel without a verified value)

## Visual Style: Industrial-Reliable (HVAC variant)

- Color: Deep blue (#1e40af), red (#dc2626) accents, professional gray
- Thermostat/cooling iconography
- Clean, trustworthy appearance

## Taglines/Copy Patterns

- Good: "Keeping {{city}} comfortable. Trusted local HVAC service."
- Bad: "Quality HVAC services" (too generic)

## Services Section Rules

- List only services present in the verified brief (e.g. repair, installation, maintenance, ductwork, air quality)
- Never display a starting price, diagnostic fee, financing option, seasonal promotion, or emergency-availability claim that is not a verified field

## Trust Section Rules

- Display certifications, licenses, insurance status, years in business, ratings, and review counts only when supplied as verified fields
- Never imply technician credentials (e.g. certifications, licensure) that are not verified
- Never display an emergency-availability claim (e.g. around-the-clock service) unless verified

## Mobile-First Requirements

- Primary verified contact channel sticky on mobile
- Click-to-call prominent (only when {{phone}} is verified)
