## ADDED Requirements

### Requirement: WhatsApp Session Login
The system SHALL provide an operator command that links a WhatsApp Web session by QR code and stores the session credentials in a configured local data directory.

#### Scenario: QR login stores session credentials
- **GIVEN** no valid WhatsApp session exists in the configured session directory
- **WHEN** an operator runs the WhatsApp login command and scans the QR code successfully
- **THEN** the system saves Baileys multi-file auth state under the configured session directory
- **AND** the saved session can be reused by the WhatsApp listener command without scanning a new QR code

#### Scenario: Unsafe session directory is rejected
- **GIVEN** the configured WhatsApp session directory resolves outside the allowed application data path
- **WHEN** the operator runs the WhatsApp login command
- **THEN** the command exits with an error
- **AND** no WhatsApp credentials are written to the unsafe path

### Requirement: WhatsApp Listener Startup
The system SHALL provide an operator command that starts a long-running WhatsApp listener from a previously linked session.

#### Scenario: Listener starts with valid session
- **GIVEN** a valid saved WhatsApp session exists
- **WHEN** the operator runs the WhatsApp listener command
- **THEN** the bridge connects to WhatsApp Web using the saved session
- **AND** it subscribes to inbound message events
- **AND** it does not require an interactive QR scan

#### Scenario: Listener refuses missing session
- **GIVEN** no valid WhatsApp session exists
- **WHEN** the operator runs the WhatsApp listener command
- **THEN** the command exits with a clear error instructing the operator to run the login command first

### Requirement: Registered Phone Access Gate
The system SHALL allow WhatsApp direct-message access only when the sender phone number resolves to exactly one registered Khetibadi user.

#### Scenario: Registered sender is accepted
- **GIVEN** an inbound WhatsApp direct message from a sender whose normalized E.164 phone number exists on exactly one Khetibadi user
- **WHEN** the bridge receives the message
- **THEN** the bridge resolves the sender to that user ID
- **AND** processes the message using that user's AI assistant context

#### Scenario: Unregistered sender receives registration error
- **GIVEN** an inbound WhatsApp direct message from a sender whose normalized E.164 phone number is not registered
- **WHEN** the bridge receives the message
- **THEN** the bridge replies with `Your number is not registered with Khetibadi. Please register first in the app.`
- **AND** it does not create an AI chat session
- **AND** it does not call the LLM provider

#### Scenario: Duplicate phone number is denied
- **GIVEN** an inbound WhatsApp direct message from a sender whose normalized E.164 phone number matches more than one user record
- **WHEN** the bridge receives the message
- **THEN** the bridge replies with a generic account-resolution error
- **AND** it does not create an AI chat session
- **AND** it logs a redacted duplicate-phone security event

### Requirement: WhatsApp AI Chat Routing
The system SHALL route accepted WhatsApp text messages through the same AI assistant pipeline used by dashboard chat.

#### Scenario: Accepted text message receives AI reply
- **GIVEN** a registered WhatsApp sender sends a non-empty text message
- **WHEN** the bridge processes the message
- **THEN** it creates or reuses a WhatsApp-channel AI chat session scoped to the resolved user
- **AND** it submits the message to the existing AI assistant response pipeline
- **AND** it sends the assistant's final answer back to the same WhatsApp direct chat
- **AND** the user message and assistant response are persisted with the resolved user ownership

#### Scenario: Empty message is ignored with guidance
- **GIVEN** a registered WhatsApp sender sends an empty text message or unsupported non-text-only message
- **WHEN** the bridge processes the message
- **THEN** it sends a short guidance reply asking the user to send a text question
- **AND** it does not call the LLM provider

#### Scenario: AI service failure is visible to user
- **GIVEN** the AI assistant pipeline fails or times out
- **WHEN** the bridge processes an accepted WhatsApp message
- **THEN** it replies with a temporary failure message asking the user to try again
- **AND** it logs the failure with redacted phone and chat identifiers

### Requirement: WhatsApp Message Feedback
The system SHALL provide WhatsApp read receipt and typing feedback for accepted inbound messages on a best-effort basis.

#### Scenario: Accepted message is marked read
- **GIVEN** the bridge accepts an inbound WhatsApp message for processing
- **WHEN** WhatsApp Web allows marking that message as read
- **THEN** the bridge calls the WhatsApp read-message API for the inbound message key
- **AND** processing continues even if the read-receipt call fails

#### Scenario: Typing is shown while processing
- **GIVEN** the bridge is processing an accepted WhatsApp message
- **WHEN** AI response generation starts
- **THEN** the bridge sends a composing presence update to the WhatsApp chat
- **AND** it sends a paused presence update after a reply or terminal error is sent

#### Scenario: Reply send failure is logged
- **GIVEN** the bridge generates an assistant reply
- **WHEN** WhatsApp message sending fails
- **THEN** the bridge logs the failure with redacted identifiers
- **AND** it does not retry indefinitely

### Requirement: WhatsApp Rate Limiting
The system SHALL rate-limit inbound WhatsApp messages before AI processing.

#### Scenario: Phone rate limit allows normal traffic
- **GIVEN** a registered WhatsApp sender has sent fewer than 20 messages in the current one-second window
- **WHEN** the next message arrives
- **THEN** the bridge allows the message to proceed to AI processing

#### Scenario: Phone rate limit blocks burst traffic
- **GIVEN** a WhatsApp sender has already sent 20 messages in the current one-second window
- **WHEN** another message arrives from the same normalized phone number
- **THEN** the bridge replies with a rate-limit message including a short retry hint
- **AND** it does not create an AI chat session
- **AND** it does not call the LLM provider

#### Scenario: Global bridge safeguards protect dependencies
- **GIVEN** the bridge-wide concurrency or queue limit is exhausted
- **WHEN** an otherwise valid WhatsApp message arrives
- **THEN** the bridge replies with a temporary busy message
- **AND** it does not start additional LLM work beyond the configured global cap

### Requirement: WhatsApp Beta User Phone Entry
The system SHALL support beta WhatsApp access by letting users enter their phone number through normal registration or account settings flows.

#### Scenario: Test user enters phone during registration
- **GIVEN** a tester is creating a Khetibadi account
- **WHEN** the tester enters a valid phone number during registration
- **THEN** auth stores the normalized phone number on the created user account
- **AND** WhatsApp messages from that number resolve to the created user

#### Scenario: Existing user enters phone in account settings
- **GIVEN** a tester already has a Khetibadi account without a phone number
- **WHEN** the tester adds a valid phone number in account settings
- **THEN** auth stores the normalized phone number on that user account
- **AND** WhatsApp messages from that number resolve to the updated user

#### Scenario: Duplicate phone entry is rejected
- **GIVEN** a tester enters a phone number already assigned to another user
- **WHEN** registration or account settings saves the phone number
- **THEN** the system shows a duplicate-phone validation error
- **AND** the phone number is not assigned to the tester's account

### Requirement: WhatsApp Privacy and Logging
The system SHALL avoid exposing WhatsApp credentials, full phone numbers, or full message bodies in logs and committed files.

#### Scenario: Logs redact sensitive WhatsApp data
- **GIVEN** the bridge logs a WhatsApp event
- **WHEN** the log event includes sender or chat context
- **THEN** full phone numbers, JIDs, message bodies, and credential paths are omitted or redacted
- **AND** logs include only non-sensitive correlation IDs needed for debugging

#### Scenario: Session files are not committed
- **GIVEN** WhatsApp session credentials exist in the configured local data directory
- **WHEN** repository status is checked
- **THEN** the session credential files are ignored by git
