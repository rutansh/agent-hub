---
name: review-literature
description: Produce a concise, citation-backed literature review brief on a drug, target, or indication from provided papers. Use when the user supplies abstracts or papers and asks for a synthesis.
---

# Literature Review Brief

## When to use

The user provides several papers or abstracts (or a topic plus sources) and wants
a synthesized brief.

## Steps

1. Restate the research question in one sentence.
2. For each source, record: citation, study type, population/model, key finding.
3. Group findings into themes (e.g. efficacy, safety, mechanism, gaps).
4. Note agreement and conflict between sources explicitly.
5. Rate overall evidence strength: strong / moderate / limited, with one sentence
   of justification (study design, sample size, consistency).
6. End with **Open questions** and suggested next searches.

## Output format

- Question
- Key findings by theme (each claim followed by a citation like `[Smith 2024]`)
- Conflicts and limitations
- Evidence strength
- Open questions

## Guardrails

- Only cite sources the user provided. If a claim has no supporting source, say so.
- Do not fabricate references, DOIs, or statistics.
