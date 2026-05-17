# Change Proposal: Dashboard Soft Craft UI and Auth Refresh Bootstrap

## ID: dashboard-soft-craft-auth-refresh
## Status: Draft
## Date: 2026-05-24

## Why

The runnable dashboard is functionally wired through the auth gateway, but browser
verification exposed two product gaps:

- protected routes lose the in-memory access token after a hard refresh and redirect
  to login before attempting the HttpOnly refresh cookie flow;
- the current dashboard visuals are inconsistent with the approved Stitch direction.

The user approved the starred Stitch "Soft Craft Refinement" pages as the source of
truth for the real app styling. The implementation should apply that traditional
Indian agricultural design language while preserving the already verified gateway API
integration.

## What Changes

- Add an async auth bootstrap path for protected dashboard routes: if memory auth is
  empty, call `POST /auth/refresh` with credentials before redirecting.
- Remove hardcoded demo values from login and register forms.
- Apply the approved Stitch Soft Craft design system to shared UI primitives, auth
  pages, dashboard shell, and all dashboard feature pages.
- Keep all browser API calls routed only through `VITE_API_BASE_URL`.
- Verify the result with lint/type-check/build and Playwright using one reusable test
  account.

## Non-goals

- No new backend persistence work in this change.
- No live mandi/AGMARKNET ingestion implementation in this change.
- No direct downstream service URLs in the dashboard.

## Design Source of Truth

Use the user's starred Stitch project selections:

- `87b69e30fd624a7ba778808ce3f988ae` — Dashboard Soft Craft Refinement overview/sidebar
- `85815a2d9d3e4741b0807ddfd11f370c` — Login
- `9316306c9ac143a8bf4d06d01ea4d037` — My Farms
- `5404d9c2914a4ee383f17ad8e5bb0c91` — Crop Advisor
- `491d5f52277049debb881abfbfa15fe9` — Disease Scan
- `1632b3689c0d45d18adfac9339f2fdde` — Market
- `11cc895b68924005a4f44ea2a8050353` — AI Assistant
- `cdc023e2cd9f4785ab6595feb04125fa` — Settings

## Market Data Note

This change will document the live market data keys still needed for future real
market ingestion: a data.gov.in/AGMARKNET API key and the confirmed mandi price
resource endpoint or resource ID. The current app remains a seeded runnable vertical
slice until that integration is implemented.
