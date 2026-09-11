# Dropout-Risk Hotspot Mapper

**AI with Education — Horizon Round 1 submission**

## The problem

In Karnataka, real 2019-20 UDISE+ data puts secondary-level dropout at
**17.8%** — nearly one in five students who reach grade IX don't finish
grade X. That number isn't from a slide; it's computed live by this
project's own pipeline from real government cohort data, and it lines
up closely with a published national estimate (~17%, PLOS ONE 2023) —
two independent numbers landing in the same place.

Dropout isn't evenly spread. It concentrates — in specific districts,
specific school types, specific infrastructure gaps. The hard problem
isn't knowing dropout is a crisis; it's knowing **where to send limited
resources first.**

## What we built

A three-layer tool that goes from "where is the problem" to "what do
we do about it," built entirely on real data:

1. **A state-wide risk map.** Every one of Karnataka's 74,309 schools,
   real UDISE+ locations, scored on a transparent risk model and
   shown two ways at once: a district choropleth for the big picture,
   and fine-grained hotspot cells (~8km, tuned to avoid the trap of
   just re-detecting where schools happen to be dense) for where to
   actually look closer.
2. **A resource-placement optimizer.** Given a budget of K mobile
   tutoring units, an integer linear program (not a heuristic) decides
   where to base them to cover the most risk-weighted schools — with a
   geographic-equity constraint so a state doesn't dump every unit
   into its two biggest cities. We benchmark the optimizer against a
   standard greedy heuristic on our own data and show the gap live, in
   the app, rather than asserting the optimizer is better.
3. **A responsible-AI layer, not an afterthought.** Every score is at
   school or district level, never a named child. The interface states
   outright, in-app, what's measured and what's a documented modeling
   choice — because a false-precise dropout score is worse than an
   honest, useful proxy.

## Why this is harder than it looks (and why that's the point)

Two real engineering findings that shaped the build, kept in because
they're the honest story:

- **A naive port of a proven pattern was wrong, and we caught it.**
  The first hotspot-detection pass directly reused a patrol-hotspot
  clustering approach from an earlier project. It failed instructively:
  parking violations are *events*, so density means "more problems."
  Schools are *fixed infrastructure* — density mostly just means "more
  people live here." The fix (grid-cell relative risk vs. a naive
  density cluster) is a small idea with a real, visible payoff: 20
  clean, spatially meaningful hotspots instead of one 53,000-school
  blob or 1,900 meaningless micro-clusters.
- **"Real data" turned out to be reachable, just not the obvious way.**
  The build environment couldn't reach India's live open-data portals.
  Rather than fall back to synthetic placeholders, we found that a
  public GitHub repo had already scraped the exact UDISE+ indicators
  needed — real functional-toilet, library, computer, and internet
  access, for all 34 districts, 2019-20. That real data is what
  produces the 17.8% cross-check above. Feasibility, in other words,
  wasn't assumed — it was tested, failed once, and solved differently.

## What's real, what's a documented choice

| Layer | Status |
|---|---|
| School locations, categories, management type | Real (UDISE+, `datameet/udise_schools`) |
| District infrastructure gaps (toilets, library, computer, internet) | Real, 2019-20 (`thejeshgn/udise-report-data-downloader`) |
| District boundaries | Real (2011 Census, `datameet/maps`), reconciled against UDISE+'s different district split — checked, not assumed |
| Rural/transition-risk rule, and how the two real signals are weighted | Documented modeling choices, not fitted to outcomes |

We say this in the app, not just in a README, because a tool that
scores dropout risk should not be the one thing in the room being
opaque about its own limits.

## Tech stack

Python (FastAPI, pandas, scikit-learn, PuLP/CBC for the ILP) on the
backend; vanilla JS + Leaflet on the frontend, no build step, Leaflet
vendored locally so the demo doesn't depend on a CDN being up in the
room. No database — 74k rows is small enough to score and cluster once
at startup and serve from memory.

## What's next

Real school-level (not just district-level) infrastructure data, once
the live UDISE+ portal is reachable. Real road-routing distance for
the deployment radius, replacing the current straight-line estimate.
Both are flagged honestly as open, not papered over.
