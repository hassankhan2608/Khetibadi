# Auth Specification Delta

## Modified Requirements

### Requirement: Token Refresh

The system SHALL allow access token renewal using a valid refresh token without requiring re-login.

#### Scenario: Dashboard bootstrap refresh

- GIVEN the dashboard sends `POST /auth/refresh` with a valid refresh cookie
- WHEN the in-memory access token was lost on page reload
- THEN auth returns a fresh access token and public user profile
- AND the dashboard can restore the authenticated session without requiring another login

#### Scenario: Refresh failure does not recurse indefinitely

- GIVEN the refresh cookie is missing, expired, or invalid
- WHEN the dashboard calls `POST /auth/refresh`
- THEN the request fails once with an unauthorized response
- AND the frontend clears memory auth and redirects to login without retry loops
