## MODIFIED Requirements

### Requirement: User Registration
The system SHALL allow new users to register with a unique email, an optional unique normalized phone number, and a password that meets strength requirements.

#### Scenario: Successful registration
- GIVEN an email not already in the database
- WHEN a `POST /auth/register` request is made with valid email and password
- THEN the user record is created with a bcrypt-hashed password
- AND a `201 Created` response is returned with the user's public profile (no password field)

#### Scenario: Successful registration with phone number
- GIVEN an email not already in the database
- AND a phone number not already assigned to another user
- WHEN a `POST /auth/register` request is made with valid email, password, and phone number
- THEN the phone number is normalized to E.164 before storage
- AND the user record is created with the normalized phone number
- AND a `201 Created` response is returned with the user's public profile (no password field)

#### Scenario: Duplicate email
- GIVEN an email already registered
- WHEN `POST /auth/register` is called with that email
- THEN `409 Conflict` is returned with `{"error": "email_taken"}`
- AND no user record is created or modified

#### Scenario: Duplicate phone number
- GIVEN a normalized phone number already assigned to another user
- WHEN `POST /auth/register` is called with that phone number
- THEN `409 Conflict` is returned with `{"error": "phone_taken"}`
- AND no user record is created or modified

#### Scenario: Weak password
- GIVEN a password shorter than 8 characters or missing an uppercase letter
- WHEN `POST /auth/register` is called
- THEN `400 Bad Request` is returned with field-level validation details

#### Scenario: Invalid email format
- GIVEN a malformed email string (e.g. "notanemail")
- WHEN `POST /auth/register` is called
- THEN `400 Bad Request` is returned with `{"field": "email", "message": "invalid format"}`

#### Scenario: Invalid phone number format
- GIVEN a phone number that cannot be normalized to E.164
- WHEN `POST /auth/register` is called with that phone number
- THEN `400 Bad Request` is returned with `{"field": "phone", "message": "invalid format"}`
- AND no user record is created or modified

## ADDED Requirements

### Requirement: User Phone Number Storage
The auth service SHALL store user phone numbers as normalized E.164 values and SHALL enforce uniqueness for non-null phone numbers.

#### Scenario: Phone number normalization
- **GIVEN** a user phone number is submitted in a supported local or international format
- **WHEN** auth validates the phone number
- **THEN** it stores the number in E.164 format
- **AND** it never stores formatting characters such as spaces or hyphens

#### Scenario: Unique phone constraint
- **GIVEN** a normalized phone number is already assigned to one user
- **WHEN** another user attempts to store the same normalized phone number
- **THEN** auth rejects the change with a conflict error
- **AND** the existing user's phone number remains unchanged

### Requirement: Internal User Lookup By Phone
The auth service SHALL expose an internal-only lookup contract that resolves a normalized phone number to a user identity for trusted backend callers.

#### Scenario: Phone lookup returns user identity
- **GIVEN** a trusted backend caller provides a normalized E.164 phone number assigned to exactly one user
- **WHEN** it calls the internal phone lookup contract
- **THEN** auth returns the user ID and public identity fields required for downstream HMAC identity
- **AND** it does not return password hash or refresh-token data

#### Scenario: Phone lookup not found
- **GIVEN** a trusted backend caller provides a normalized E.164 phone number not assigned to any user
- **WHEN** it calls the internal phone lookup contract
- **THEN** auth returns a not-found result
- **AND** it does not reveal whether any email account exists for the sender

#### Scenario: Phone lookup requires service authentication
- **GIVEN** a caller does not provide valid service-to-service authentication
- **WHEN** it calls the internal phone lookup contract
- **THEN** auth returns `401 Unauthorized`
- **AND** no user data is returned

### Requirement: User Phone Number Update
The auth service SHALL allow authenticated users to add or update their own phone number through the normal account profile flow.

#### Scenario: Authenticated user updates phone number
- **GIVEN** an authenticated user provides a valid phone number not assigned to another user
- **WHEN** the user saves account profile changes
- **THEN** auth normalizes the phone number to E.164
- **AND** stores it on that user's account
- **AND** returns the updated public profile

#### Scenario: Authenticated user update rejects duplicate phone
- **GIVEN** an authenticated user provides a phone number already assigned to another user
- **WHEN** the user saves account profile changes
- **THEN** auth returns `409 Conflict` with `{"error": "phone_taken"}`
- **AND** the user's existing phone number remains unchanged

#### Scenario: Authenticated user update rejects invalid phone
- **GIVEN** an authenticated user provides a phone number that cannot be normalized to E.164
- **WHEN** the user saves account profile changes
- **THEN** auth returns `400 Bad Request` with `{"field": "phone", "message": "invalid format"}`
- **AND** the user's existing phone number remains unchanged
