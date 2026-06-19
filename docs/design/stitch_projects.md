# Stitch Projects

## Batch 001 — Premium Detailing Gold Standard

Date: 2026-05-13

Project:
- `projects/3434553641374076192`
- Title: Autowebdelivery Premium Detailing Gold Standard

Design system:
- `assets/a028c0c88591415ba78d3543f41b16cb`
- Tokens: dark obsidian, surface `#0d1516`, primary `#c3f5ff`, primary-container `#00e5ff`, secondary `#e9c349`
- Fonts: Metropolis (display), Hanken Grotesk (body), Geist (labels)

### Screen 1 (REJECTED — unsafe content)

- Screen: `134bc4fefe4646a38f35b1bd48a4aa4b`
- Reason: fake phone `(469) 555-0123`, badges "5-STAR SERVICE" / "CERAMIC PRO CERTIFIED", unsupported "Premier Studio" / "collectors trust"
- Kept for reference only

### Screen 2 — Mobile (GOLD STANDARD — Phase 06 PASS)

- Screen: `8cb98d2b1fe24678b0ca1e0f88f50acf`
- Title: `Apex Auto Detail - Compliant Mobile Landing Page`
- Size: 780 x 15356px
- Local: `artifacts/stitch/batch_001/mobile/index.html`
- Manual patch: stripped residual "CERAMIC PRO CERTIFIED" trust-strip section (Stitch edit left orphaned element)
- Phase 06: PASS (0 unsupported claims, 0 fake phones)

### Screen 3 — Desktop (GOLD STANDARD — Phase 06 PASS)

- Screen: `46a2424bf0d44a63930dd79c37c72ab4`
- Title: `Apex Auto Detail - Premium Desktop Landing Page`
- Size: 2560 x 10234px
- Local: `artifacts/stitch/batch_001/desktop/index.html`
- Phase 06: PASS (0 unsupported claims, 0 fake phones)

### Content audit (both screens pass all blockers)

- Zero fake 555-01xx phone numbers
- Zero generic phone patterns
- Zero "5-STAR SERVICE" / "CERAMIC PRO CERTIFIED" / "Premier Studio" / "collectors trust" / "award-winning" / "guarantee" / "#1" / "official partner"
- Contact section: "Contact us for a quote" (no placeholder phone)
- CTAs: GET QUOTE, GET INSTANT QUOTE, SELECT PACKAGE, BOOK NOW, REQUEST YOUR QUOTE, VIEW GALLERY
- Sections: Studio Services (Ceramic Coating, Paint Correction), Investment Packages (Interior Reset, Signature Ceramic, Concourse Prep), The 4-Step Protocol (Decontaminate, Correct, Protect, Perfect), Ready to Elevate Your Vehicle?
- Footer: Services links, Studio Info, Mon-Sat 8:00 AM - 6:00 PM

Visual design:
- Dark luxury automotive aesthetic intact
- Glass-panel cards, ceramic teal CTAs, editorial spacing
- Premium product-quality: sellable to auto detailing business owners

Known Stitch limitation:
- Stitch edit API may leave orphaned HTML elements from removed badges/sections. Manual HTML patch required as post-processing step. Document this in pipeline automation.

Next:
- Wire gold standard into autowebdelivery pipeline as template (HTML post-processing + Stitch download automation)
- Generate more lead variants for batch 001
- Implement real browser screenshot capture (Phase 05.5 Playwright)
- Vercel deploy for public preview links

### Batch 001 Lead Pages (all Phase 06 PASS)

| Lead | Screen ID | Size | Path |
|------|-----------|------|------|
| Frisco Mobile Detailing | `a613f13fa6d7411da83ac0281f2ad1f0` | 16KB | `artifacts/stitch/batch_001/leads/frisco-mobile-detailing/` |
| On Time Mobile Detailing | `4bdb41c357444de28b06b9011ea9f1ff` | 15KB | `artifacts/stitch/batch_001/leads/on-time-mobile-detailing/` |
| Xceptional Details | `ffde4dd1da7d4fee86a79c9ef78ba5d3` | 21KB | `artifacts/stitch/batch_001/leads/xceptional-details/` |

All three pass Phase 06: zero unsupported claims, zero fake phones.

### Public Preview Links (Vercel)

| Lead | URL | Status |
|------|-----|--------|
| Frisco Mobile Detailing | https://frisco-mobile-detailing.vercel.app | LIVE |
| On Time Mobile Detailing | https://on-time-mobile-detailing.vercel.app | LIVE |
| Xceptional Details | https://xceptional-details.vercel.app | LIVE |

Deployed via `/opt/homebrew/bin/vercel --yes --prod` from each lead directory. Vercel Hobby tier.
