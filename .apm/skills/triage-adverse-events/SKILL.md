---
name: triage-adverse-events
description: Triage adverse event reports by seriousness and expectedness and flag cases needing expedited review. Use when the user shares AE narratives, case reports, or safety listings.
---

# Adverse Event Triage

## When to use

The user provides one or more adverse event (AE) narratives or a safety listing
and wants them categorized and prioritized.

## Steps

1. For each case, capture: patient age/sex (if given), suspect product, event
   term(s), onset date, outcome, reporter type.
2. Assess **seriousness** against standard criteria: death, life-threatening,
   hospitalization, disability, congenital anomaly, other medically important.
3. Assess **causality** wording as written by the reporter (do not assign your own
   final causality; flag it as "reporter-assessed" or "not assessed").
4. Assess **expectedness** only if a reference safety document (label / IB) is
   provided. Otherwise mark "unknown - reference document needed".
5. Assign a triage priority:
   - **P1**: serious AND (unexpected OR fatal/life-threatening)
   - **P2**: serious and expected
   - **P3**: non-serious
6. Output a table sorted by priority, then a short list of missing information
   needed to complete each P1/P2 case.

## Guardrails

- Final regulatory classification must be made by a qualified safety professional.
- Do not invent dates, doses, or outcomes missing from the narrative.
- Treat patient data as confidential; do not echo identifiers unnecessarily.
