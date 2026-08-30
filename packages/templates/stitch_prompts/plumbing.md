# Stitch Prompt Template: Plumbing

Facts-only policy: this prompt contains structure, layout, and tone guidance only.
Every business fact must come from a {{verified_field}} placeholder supplied with the
prompt. If a verified field is absent, instruct the model to omit that element -
never to invent a default value. Never display a `$` amount unless it comes from a
verified field.

Design a premium single-page business website for {{business_name}}, a plumbing service in {{city}}.

## Layout Structure

1. **HERO section**: large headline focused on the verified service offering in {{city}}, business name prominent, phone CTA "Call Now: {{phone}}"
2. **SERVICES grid**: 3-4 service cards with icons, one per verified service from the brief, with name and description only - do not display prices unless a verified price is supplied
3. **TRUST section**: display {{rating}} stars rating from {{review_count}} reviews (only if both are verified; otherwise omit the rating block entirely), mention license number only if supplied as a verified field, "Serving {{city}} since {{years}}" (only if {{years}} is verified; otherwise omit)
4. **LOCATION**: {{address}} in {{city}} (only if {{address}} is verified; otherwise show the service area only), service area map iframe
5. **CTA section**: "Contact {{business_name}} - call {{phone}} or fill form" (omit any channel without a verified value; never display a promotional discount that is not a verified field)

## Visual Style: Industrial-Reliable

- Color palette: Navy blue (#1e3a8a), orange (#ea580c), white
- Font: Bold sans-serif for headlines (Inter or Roboto), clean body text
- Layout: Sharp edges, high contrast, clear sections
- Hero image: Professional plumbing van or technician working

## Taglines/Copy Patterns

- Good: "Trusted plumbing service in {{city}}. Call {{phone}}."
- Bad: "Professional Plumbing Services" (too generic)

## Services Section Rules

- List only services present in the verified brief (e.g. drain cleaning, water heater, leak detection, sewer line service)
- Never display a starting price, flat rate, or minimum charge that is not a verified field
- Never display an emergency-availability claim (e.g. around-the-clock service) unless verified

## Mobile-First Requirements

- Fast loading (Tailwind CDN)
- Click-to-call buttons prominent (only when {{phone}} is verified)
- No stock photos - use actual business photos where available
