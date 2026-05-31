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
