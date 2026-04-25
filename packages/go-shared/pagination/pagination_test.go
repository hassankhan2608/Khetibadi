package pagination

import (
	"testing"

	"github.com/stretchr/testify/require"
)

type stubReader map[string]string

func (s stubReader) Query(key string) string { return s[key] }

func TestParse(t *testing.T) {
	cases := []struct {
		name string
		in   stubReader
		want Page
	}{
		{"defaults when empty", stubReader{}, Page{Page: 1, Limit: 20, Offset: 0}},
		{"valid page and limit", stubReader{"page": "3", "limit": "25"}, Page{Page: 3, Limit: 25, Offset: 50}},
		{"negative page falls back", stubReader{"page": "-2", "limit": "10"}, Page{Page: 1, Limit: 10, Offset: 0}},
		{"zero limit falls back", stubReader{"page": "2", "limit": "0"}, Page{Page: 2, Limit: 20, Offset: 20}},
		{"limit above max clamps", stubReader{"limit": "1000"}, Page{Page: 1, Limit: 100, Offset: 0}},
		{"non-numeric page", stubReader{"page": "abc"}, Page{Page: 1, Limit: 20, Offset: 0}},
		{"non-numeric limit", stubReader{"limit": "abc"}, Page{Page: 1, Limit: 20, Offset: 0}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			require.Equal(t, tc.want, Parse(tc.in))
		})
	}
}
