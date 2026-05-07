# Auth Specification

## Purpose

User registration, login, JWT session management, public API gateway routing, and
downstream service authentication. No OAuth — email and password only.

## Requirements

### Requirement: User Registration

The system SHALL allow new users to register with a unique email and a password that meets strength requirements.

#### Scenario: Successful registration
- GIVEN an email not already in the database
- WHEN a `POST /auth/register` request is made with valid email and password
- THEN the user record is created with a bcrypt-hashed password
- AND a `201 Created` response is returned with the user's public profile (no password field)

#### Scenario: Duplicate email
- GIVEN an email already registered
- WHEN `POST /auth/register` is called with that email
- THEN `409 Conflict` is returned with `{"error": "email_taken"}`
- AND no user record is created or modified

#### Scenario: Weak password
- GIVEN a password shorter than 8 characters or missing an uppercase letter
- WHEN `POST /auth/register` is called
- THEN `400 Bad Request` is returned with field-level validation details

#### Scenario: Invalid email format
- GIVEN a malformed email string (e.g. "notanemail")
- WHEN `POST /auth/register` is called
- THEN `400 Bad Request` is returned with `{"field": "email", "message": "invalid format"}`

---

### Requirement: User Login

The system SHALL authenticate users by email and password and issue a short-lived access token plus a long-lived refresh token.

#### Scenario: Successful login
- GIVEN a registered user with correct credentials
- WHEN `POST /auth/login` is called
- THEN an access token (JWT, 15-minute TTL) is returned in the response body
- AND a refresh token (opaque, 7-day TTL) is set as an HttpOnly, Secure, SameSite=Strict cookie
- AND the refresh token is stored hashed in the database

#### Scenario: Wrong password
- GIVEN a registered email but incorrect password
- WHEN `POST /auth/login` is called
- THEN `401 Unauthorized` is returned with `{"error": "invalid_credentials"}`
- AND no tokens are issued

#### Scenario: Unknown email
- GIVEN an email not in the database
- WHEN `POST /auth/login` is called
- THEN `401 Unauthorized` is returned — same error as wrong password to prevent email enumeration

#### Scenario: Rate limiting login
- GIVEN 5 failed login attempts from the same IP within 10 minutes
- WHEN a 6th attempt is made
- THEN `429 Too Many Requests` is returned with `Retry-After` header
- AND the block is stored in Redis with a 10-minute TTL

---

### Requirement: Token Refresh

The system SHALL allow access token renewal using a valid refresh token without requiring re-login.

#### Scenario: Valid refresh
- GIVEN a valid, non-expired refresh token in the request cookie
- WHEN `POST /auth/refresh` is called
- THEN a new access token is returned in the response body
- AND the refresh token cookie TTL is extended (sliding window)

#### Scenario: Expired refresh token
- GIVEN a refresh token past its 7-day TTL
- WHEN `POST /auth/refresh` is called
- THEN `401 Unauthorized` is returned
- AND the expired token is deleted from the database

#### Scenario: Reuse detection
- GIVEN a refresh token that was already rotated
- WHEN an old refresh token is used again
- THEN `401 Unauthorized` is returned
- AND all refresh tokens for that user are invalidated (session family revocation)

---

### Requirement: Logout

The system SHALL invalidate the session on logout.

#### Scenario: Successful logout
- GIVEN an authenticated user
- WHEN `POST /auth/logout` is called
- THEN the refresh token is deleted from the database
- AND the cookie is cleared (Set-Cookie with Max-Age=0)
- AND `200 OK` is returned

---

### Requirement: JWT Structure

Access tokens SHALL contain only the minimum claims needed by downstream services.

#### Scenario: Token payload
- GIVEN a successfully logged-in user
- WHEN the access token is decoded
- THEN it contains: `sub` (user UUID), `email`, `iat`, `exp`
- AND it does NOT contain the password hash, full profile, or role permissions

---

### Requirement: HMAC Downstream Signing

The auth service SHALL attach HMAC-signed headers to every proxied request so downstream Go and Python services can verify identity without a database call.

#### Scenario: HMAC header on authenticated request
- GIVEN a valid access token in the Authorization header
- WHEN auth forwards a request to `farm-service`
- THEN it attaches `X-User-ID: <uuid>` and `X-HMAC-Signature: <hmac-sha256>` headers
- AND the signature covers `user_id + timestamp` with the shared secret

#### Scenario: Downstream service rejects tampered header
- GIVEN `X-User-ID` was modified in transit
- WHEN farm-service verifies the HMAC signature
- THEN signature mismatch causes `401 Unauthorized`

---

### Requirement: Public API Gateway Routing

Auth SHALL be the single browser-facing API gateway. It SHALL handle auth routes
locally and reverse proxy all other protected API routes to internal services over
the Docker network.

#### Scenario: Browser uses a single API origin
- GIVEN the dashboard is running in the browser
- WHEN it performs login, farm, market, ML, or chat requests
- THEN every request is sent to the auth gateway origin
- AND the browser never calls downstream service ports directly

#### Scenario: Route prefixes map to internal services
- GIVEN a request reaches auth with a valid session when required
- WHEN the path starts with `/farms/`
- THEN auth proxies to `farm-service:8001`
- WHEN the path starts with `/market/`
- THEN auth proxies to `market-service:8002`
- WHEN the path starts with `/ml/crop/`
- THEN auth proxies to `ml-crop:8010`
- WHEN the path starts with `/ml/vision/`
- THEN auth proxies to `ml-vision:8011`
- WHEN the path starts with `/ai/chat/`
- THEN auth proxies to `ai-chat:8012`

#### Scenario: Downstream ports stay private
- GIVEN Docker Compose starts the full stack
- WHEN a browser accesses the application
- THEN only the dashboard and auth gateway are published for HTTP traffic
- AND farm-service, market-service, ml-crop, ml-vision, and ai-chat remain internal

---

### Requirement: Password Change

Authenticated users SHALL be able to change their password by providing the current password.

#### Scenario: Successful change
- GIVEN an authenticated user provides correct current password and a valid new password
- WHEN `PUT /auth/password` is called
- THEN the password is updated
- AND all existing refresh tokens for that user are revoked

#### Scenario: Wrong current password
- GIVEN an authenticated user provides an incorrect current password
- WHEN `PUT /auth/password` is called
- THEN `403 Forbidden` is returned
- AND the password is not changed
