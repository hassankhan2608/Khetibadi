# Dashboard Specification Delta

## Modified Requirements

### Requirement: Authentication Flow

The system MUST enforce authentication on all routes except `/login` and `/register`.

#### Scenario: Protected route hard refresh with valid refresh cookie

- GIVEN the user previously logged in and still has a valid HttpOnly refresh cookie
- AND the in-memory access token was lost due to a hard refresh or direct navigation
- WHEN TanStack Router evaluates a protected `/dashboard` route
- THEN the dashboard calls `POST /auth/refresh` through the single API gateway
- AND stores the returned access token in memory
- AND allows the protected route to render without showing the login page

#### Scenario: Protected route hard refresh without valid refresh cookie

- GIVEN the in-memory access token is missing
- AND `POST /auth/refresh` fails
- WHEN TanStack Router evaluates a protected `/dashboard` route
- THEN the user is redirected to `/login`

#### Scenario: Auth forms start empty

- GIVEN a user opens `/login` or `/register`
- WHEN the form renders
- THEN the email, password, and name fields are empty
- AND any example values are shown only as placeholders or helper text

### Requirement: Soft Craft Visual System

The dashboard MUST use the approved Stitch Soft Craft Refinement visual direction.

#### Scenario: App visual language

- GIVEN any dashboard page renders
- THEN the UI uses a dusty mitti/earth background, deep crop green primary surfaces,
  turmeric/marigold accents, and terracotta details
- AND cards use warm handmade-paper surfaces with soft borders and consistent spacing
- AND the sidebar, auth pages, and feature pages share the same navigation and surface
  treatment

#### Scenario: Single gateway origin preserved

- GIVEN the redesigned dashboard performs auth, farm, market, ML, vision, or chat calls
- WHEN browser requests are inspected
- THEN API requests still target only `VITE_API_BASE_URL`
- AND no frontend code exposes direct downstream service origins
