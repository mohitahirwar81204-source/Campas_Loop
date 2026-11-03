# CampusLoop Verification Report

Verified on **November 3, 2026** against `CODE_CRACK_3_3rd_Yr_Problem_Statement.pdf`.

## PDF requirement audit

| PDF requirement | Status | Evidence |
|---|---|---|
| Load and display listings | Pass | SQLite-backed marketplace renders 20 initial records |
| Add or edit a listing locally | Pass | Add/edit modal, validated FastAPI endpoints, local SQLite persistence |
| Search by name | Pass | Title, category, condition, plural alias, exact-item, and combined-token searches exercised in browser QA |
| Filter by category | Pass | Marketplace category selector exercised in browser QA |
| Filter by maximum budget | Pass | Recommendation and marketplace budget inputs stay synchronized; “within budget” uses the buyer's live value |
| Price indicator | Pass | Selling price/original price ratio shown per listing |
| Ranking uses price, age, and condition | Pass | All three normalized components and weights are shown |
| Top three eligible products | Pass | Exactly three cards returned when 3+ products are eligible |
| Reason for each recommendation | Pass | Budget saving, ratio, age, and condition explanation on every card |
| Within-category anomaly rule | Pass | Flag when price differs by more than 35% from category median |
| Flag is not proof of fraud | Pass | Explicit warning appears beside analysis and marketplace |
| Affordability versus condition | Pass | Decision Lab compares both modes with the same data and budget |
| Missing values | Pass | Neutral age/condition score; missing original price omits only ratio |
| Identical scores | Pass | Condition, price, age, and listing-ID tie-break sequence |
| Duplicate listings | Pass | Import skips exact duplicates, reports them separately from invalid rows, and ranking shows each exact product once |
| Too few comparable items | Pass | No anomaly flag with fewer than three category listings |
| Similar categories only | Pass | Recommendation selector requires one category; no cross-category ranking |
| Formula and assumptions documented | Pass | Formula modal, README, API response, and this report |
| No payment/authentication/ML | Pass | None implemented or assumed |
| Professional marketplace UX | Pass | Sticky global search, category rail, product cards, sorting, filters, shortlist, responsive desktop/mobile layout |

## Automated verification

Analytical test suite:

```text
8 tests passed
```

Coverage includes anomaly rules, small categories, missing data, priority changes, budget/category eligibility, ties, exact-duplicate handling, and PDF-style CSV columns.

Live browser suite (desktop and mobile marketplace storefront):

```text
Browser QA: PASS
Priority shift: Laptop E -> Laptop D
Desktop category-aware search/synchronized budget/import/listing/filter/dialog/add/edit checks: PASS
Mobile overflow and responsive recommendation checks: PASS
Browser console errors: none
```

Live API checks also confirmed homepage HTTP 200, health status, product CRUD, CSV import, cleanup, and three-result recommendation responses.

## Ranking assumptions

- Only products within the chosen category and buyer budget are eligible.
- Affordability score: `100 × (1 - price / budget)`, clamped to 0–100.
- Age score: `100 × (1 - age / 10)`, clamped to 0–100.
- Condition: Excellent 100, Good 80, Average 60, Fair 35, Poor 15.
- Missing age or condition receives a neutral 50; this is disclosed in the explanation.
- Original price is used for the displayed price ratio, not invented when missing.
- Category median flags are review signals only and never fraud claims.
