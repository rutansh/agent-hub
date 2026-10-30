---
name: clinical-trial-summary
description: Summarize a clinical trial record into a structured, plain-language brief. Use when the user shares a trial protocol, ClinicalTrials.gov entry, or results text and wants a digest.
---

# Clinical Trial Summary

## When to use

The user provides a clinical trial document (protocol, registry entry, results
section) and asks for a summary, digest, or "what is this trial about".

## Steps

1. Identify the trial: registry ID (e.g. NCT number), title, sponsor, phase.
2. Extract, in this order:
   - **Objective** and primary/secondary endpoints
   - **Population**: key inclusion/exclusion criteria, planned and actual enrollment
   - **Design**: randomization, blinding, arms, comparator, duration
   - **Results** (only if present): primary endpoint outcome, safety signals
3. Write the brief using the template below.
4. List anything you could not find under **Not stated in source**. Never infer
   numbers, p-values, or outcomes that are not in the document.

## Output template

```
Trial: <title> (<registry id>) - Phase <n> - Sponsor: <sponsor>
Objective: <1-2 sentences>
Population: <who, how many>
Design: <arms, blinding, duration>
Primary endpoint: <endpoint> -> <result or "not reported">
Safety: <notable adverse events or "not reported">
Not stated in source: <list>
```

## Guardrails

- Quote numbers exactly as written in the source.
- This is a summary aid, not medical advice.
