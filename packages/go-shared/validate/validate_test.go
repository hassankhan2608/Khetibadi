package validate

import (
	"errors"
	"testing"

	"github.com/go-playground/validator/v10"
	"github.com/stretchr/testify/require"
)

type sample struct {
	Email string `json:"email" validate:"required,email"`
	Age   int    `json:"age" validate:"gte=0,lte=130"`
}

func TestStruct_ValidPasses(t *testing.T) {
	require.NoError(t, Struct(sample{Email: "a@b.co", Age: 30}))
}

func TestStruct_InvalidReportsJSONFieldName(t *testing.T) {
	err := Struct(sample{Email: "not-an-email", Age: 30})
	require.Error(t, err)
	var verrs validator.ValidationErrors
	require.True(t, errors.As(err, &verrs))
	require.Equal(t, "email", verrs[0].Field())
}

func TestV_ReturnsSingletonInstance(t *testing.T) {
	require.Same(t, V(), V())
}
