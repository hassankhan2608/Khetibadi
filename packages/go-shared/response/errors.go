package response

// Canonical error codes used across all services. New codes must be added here
// (not free-typed at the call site) so downstream clients can build exhaustive
// error handling.
const (
	CodeValidation     = "validation_error"
	CodeUnauthorized   = "unauthorized"
	CodeForbidden      = "forbidden"
	CodeNotFound       = "not_found"
	CodeConflict       = "conflict"
	CodeRateLimited    = "rate_limited"
	CodeUpstream       = "upstream_error"
	CodeUnavailable    = "service_unavailable"
	CodeInternal       = "internal_error"
	CodeBadRequest     = "bad_request"
	CodeUnprocessable  = "unprocessable_entity"
	CodeEmailTaken     = "email_taken"
	CodePhoneTaken     = "phone_taken"
	CodeInvalidCreds   = "invalid_credentials" //nolint:gosec // error code string, not a credential
	CodeTokenExpired   = "token_expired"
	CodeTokenInvalid   = "token_invalid"
	CodeReplayDetected = "replay_detected"
)
