# Phase 09 Manual Approval Pack Fixtures

## Input Fixtures

### complete_review_record.json
Valid review record with all required fields including both screenshots, outreach draft, and approved site.

### missing_desktop_screenshot_path.json
Record missing desktop screenshot path - should be filtered out.

### missing_mobile_screenshot_path.json
Record missing mobile screenshot path - should be filtered out.

### missing_outreach_draft.json
Record with missing outreach draft - included but draft_status shows "missing".

### site_needs_edit.json
Record where site_status is "needs_edit" - included with appropriate approval status.

## Expected Output

### review_table_expected.csv
CSV table with lead score, recipient channel, preview URL, and approval columns.

### screenshots_index_expected.json
JSON array of business slugs with both screenshot paths.

### approval_decisions_expected.json
JSON array of approval decisions with default pending status.

## Key Rules

- Both `screenshot_desktop_path` and `screenshot_mobile_path` must be present
- Legacy single `screenshot_path` is not sufficient
- Include lead score, recipient channel, preview URL, and approval columns
- Do not trigger sending or outreach automation