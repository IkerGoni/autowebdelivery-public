# Outreach Email Examples — MVP

## Purpose

Provide short, low-pressure examples for Phase 08. These are templates, not final copy. The generator must inject only verified facts and must block if required fields are missing.

## Global constraints

```text
Target length: 90–150 words
No attachments
No fake urgency
No fake partnership
No claim that the business requested the site
No negative/shaming language about the business
No invented results, awards, or service claims
Include preview URL
Include simple opt-out line
```

## Required variables

```text
business_name
preview_url
price_offer
recipient_channel
sender_name
sender_signature
```

Optional verified variables:

```text
category
area
rating
review_count
phone
maps_url
```

## Example 1 — No listed website

### Input assumptions

```text
business_name: Bright Smile Dental Clinic
category: Dental clinic
area: Chiang Mai
website_status: no_website
rating: 4.7
review_count: 86
preview_url: https://example-preview.example.com/bright-smile-dental-clinic-31a8
price_offer: $299 one-time setup
```

### Subject

```text
Small website preview for Bright Smile Dental Clinic
```

### Body

```text
Hi,

I found Bright Smile Dental Clinic on Google Maps and noticed there was no regular website listed.

I made a simple one-page preview using only public listing information, so you can see what a clean mobile-friendly site could look like:

https://example-preview.example.com/bright-smile-dental-clinic-31a8

If this is useful, I can customize it for your business and set it up for $299 one-time. No obligation.

If you are not interested, reply “no thanks” and I will not contact you again. I can also remove the preview.

Best,
[Sender name]
[Sender signature]
```

## Example 2 — Social-only business

### Input assumptions

```text
business_name: Baan Riverside Kitchen
category: Restaurant
area: Chiang Mai
website_status: social_only
rating: 4.6
review_count: 142
preview_url: https://example-preview.example.com/baan-riverside-kitchen-a92f
price_offer: $299 one-time setup
recipient_channel: facebook_message
```

### Subject

```text
Sample website page for Baan Riverside Kitchen
```

### Body

```text
Hi,

I found Baan Riverside Kitchen through your public listing/social page and made a small sample website page for the restaurant:

https://example-preview.example.com/baan-riverside-kitchen-a92f

It is only a preview and uses public listing information. The goal is to show how a simple site could make location, opening details, and contact actions easier to find.

If useful, I can customize and launch it for $299 one-time. No obligation.

Reply “no thanks” and I will not contact you again. I can also remove the preview.

Best,
[Sender name]
[Sender signature]
```

## Example 3 — Contact form version

Use when `recipient_channel = contact_form`.

```text
Hello,

I made a small one-page website preview for [business_name] using public listing information:

[preview_url]

If useful, I can customize and launch it for [price_offer]. No obligation. If this is not relevant, please ignore this message or reply no thanks through your preferred contact method.

[Sender name]
[Sender signature]
```

## Example 4 — Phone call note / script

Use when `recipient_channel = phone`. Do not pretend there was prior contact.

```text
Hi, I found [business_name] on Google Maps and made a small sample website preview using public information from the listing. Is there a good email or message channel where I can send the preview link? No obligation, and I can remove it if you are not interested.
```

## Blocked example — unknown recipient

If `recipient_channel = unknown`, Phase 08 must not create a ready-to-send draft.

```json
{
  "draft_status": "blocked",
  "blocked_reason": "recipient_channel is unknown; manual recipient discovery or override required"
}
```

## Forbidden phrases

Do not generate:

```text
Your business is losing customers
I fixed your website
You requested this preview
We are your website partner
Final notice
Guaranteed increase in bookings
Best restaurant in Chiang Mai
Trusted by thousands
```

## Review checklist for Phase 09

```text
subject is truthful
business name is correct
preview_url works
price_offer matches RunConfig
opt-out line exists
no fake relationship
no invented business facts
no pressure language
recipient channel is valid
```
