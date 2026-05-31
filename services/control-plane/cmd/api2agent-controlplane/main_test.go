package main

import (
	"testing"

	"api2agent/services/control-plane/internal/httpapi"
)

func TestRequiresLocalAdminToken(t *testing.T) {
	tests := []struct {
		name              string
		identityMode      string
		authenticatorMode string
		want              bool
	}{
		{
			name: "default local private",
			want: true,
		},
		{
			name:         "explicit local private identity",
			identityMode: httpapi.AdminIdentityModeLocalPrivate,
			want:         true,
		},
		{
			name:              "explicit local private authenticator",
			identityMode:      httpapi.AdminIdentityModeHosted,
			authenticatorMode: httpapi.AdminAuthenticatorModeLocalPrivate,
			want:              true,
		},
		{
			name:              "hosted trusted gateway",
			identityMode:      httpapi.AdminIdentityModeHosted,
			authenticatorMode: httpapi.AdminAuthenticatorModeTrustedGateway,
			want:              false,
		},
		{
			name:         "hosted without authenticator fails closed at request time",
			identityMode: httpapi.AdminIdentityModeHosted,
			want:         false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := requiresLocalAdminToken(test.identityMode, test.authenticatorMode); got != test.want {
				t.Fatalf("requiresLocalAdminToken() = %t, want %t", got, test.want)
			}
		})
	}
}

func TestParseTrustedGatewaySecrets(t *testing.T) {
	got := parseTrustedGatewaySecrets(" old-secret, new-secret ,, old-secret ")
	want := []string{"old-secret", "new-secret"}
	if len(got) != len(want) {
		t.Fatalf("parseTrustedGatewaySecrets() = %#v, want %#v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("parseTrustedGatewaySecrets() = %#v, want %#v", got, want)
		}
	}
}
