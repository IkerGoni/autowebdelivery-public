# Stitch Prompt Template: Auto Detailing

Facts-only policy: this prompt contains structure, layout, and tone guidance only.
Every business fact must come from a {{verified_field}} placeholder supplied with the
prompt. If a verified field is absent, instruct the model to omit that element -
never to invent a default value. Never display a `$` amount unless it comes from a
verified field.

Design a premium single-page business website for {{business_name}}, an auto detailing service in {{city}}.

## Layout Structure

1. **HERO section**: value headline focused on convenience, before/after photo showcase, "Book Online: {{booking_url}}" (only if {{booking_url}} is verified; otherwise omit the booking button)
2. **SERVICES**: one card per verified service from the brief, each with name and description only - do not display prices unless a verified price is supplied
3. **GALLERY**: Before/after transformation photos (grid of 4-6 images)
4. **TRUST**: {{rating}} stars from {{review_count}} happy customers (only if both are verified; otherwise omit the rating block entirely), "Mobile service - we come to your home/office"
5. **SERVICE AREA**: "Serving {{city}} and surrounding areas", map showing coverage
6. **CTA**: "Book your detail online - {{booking_url}} or call {{phone}}" (omit any channel without a verified value)

## Visual Style: Industrial-Reliable (Detailing variant)

- Dark theme preferred (#111827 background)
- Show car shine/sparkle effects
- Before/after comparison layout
- Mobile-first with large images

## Taglines/Copy Patterns

- Good: "From {{city}} to showroom shine. Book online - {{booking_url}}"
- Bad: "Professional car cleaning" (too generic)

## Services Section Rules

- List only services present in the verified brief
- If no verified price exists for a service, show name and description without any price
- Never display a starting price, price range, package tier, duration, or warranty that is not a verified field

## Trust Section Rules

- Display ratings, review counts, warranties, and guarantees only when supplied as verified fields
- Never imply certifications, insurance status, or years in business that are not verified

## Mobile-First Requirements

- Large photo focus
- Primary verified contact channel prominently displayed
- Easy online booking prominently displayed (only when {{booking_url}} is verified)
- Gallery swipe-friendly on mobile
