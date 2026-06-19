# Agent Task Prompt Index

This folder is kept for backward compatibility. Use the split task folders for new work:

```text
docs/research_tasks/        tool/repo/design research prompts
docs/implementation_tasks/  fixture-driven build prompts
```

## Correct sequencing

Do not start with full orchestration. First build and verify the fixture-based local slice:

1. Phase 02.1 website filter implementation
2. Phase 03 lead scoring implementation
3. Phase 04 business brief + recipient routing implementation
4. Phase 05 template preview generation implementation
5. Phase 06 quality gate implementation

Research prompts are useful for tool choice, but they must not block the first fixture-based implementation slice.

## Available implementation prompts

```text
docs/implementation_tasks/phase_00_setup_implementation_prompt.md
docs/implementation_tasks/phase_01_user_input_implementation_prompt.md
docs/implementation_tasks/phase_02_basic_lead_discovery_implementation_prompt.md
docs/implementation_tasks/phase_02_1_website_filter_implementation_prompt.md
docs/implementation_tasks/phase_03_lead_scoring_implementation_prompt.md
docs/implementation_tasks/phase_04_business_brief_implementation_prompt.md
docs/implementation_tasks/phase_05_preview_site_generation_implementation_prompt.md
docs/implementation_tasks/phase_06_quality_gate_implementation_prompt.md
docs/implementation_tasks/phase_07_deployment_implementation_prompt.md
docs/implementation_tasks/phase_08_outreach_generation_implementation_prompt.md
docs/implementation_tasks/phase_09_manual_approval_pack_implementation_prompt.md
docs/implementation_tasks/phase_10_manual_sending_implementation_prompt.md
docs/implementation_tasks/phase_11_monetization_tracking_implementation_prompt.md
```
