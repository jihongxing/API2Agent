package adapters

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"api2agent/services/data-plane/internal/credentials"
	"api2agent/services/data-plane/internal/snapshots"
)

func TestHttpbinIPAdapterNormalizesOrigin(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"origin":"203.0.113.42"}`))
	}))
	defer server.Close()

	result, err := HttpbinIPAdapter{Client: server.Client()}.Call(
		context.Background(),
		provider(server.URL),
		map[string]any{},
		credentials.CredentialPatch{},
	)
	if err != nil {
		t.Fatalf("call httpbin adapter: %v", err)
	}
	if result.Output["ip"] != "203.0.113.42" {
		t.Fatalf("expected normalized ip, got %#v", result.Output)
	}
	if result.StatusCode != http.StatusOK {
		t.Fatalf("expected status 200, got %d", result.StatusCode)
	}
}

func TestHttpbinIPAdapterReturnsStatusError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	result, err := HttpbinIPAdapter{Client: server.Client()}.Call(
		context.Background(),
		provider(server.URL),
		map[string]any{},
		credentials.CredentialPatch{},
	)
	if err == nil {
		t.Fatalf("expected status error")
	}
	if result.StatusCode != http.StatusInternalServerError {
		t.Fatalf("expected status 500, got %d", result.StatusCode)
	}
}

func provider(baseURL string) snapshots.ProviderCandidate {
	return snapshots.ProviderCandidate{
		ID:                "httpbin_test",
		CapabilityID:      "network.public_ip.get",
		CapabilityVersion: "0.1-migrated",
		ProviderID:        "httpbin",
		ProviderVersion:   "1.0.0",
		MappingVersion:    "1.0.0",
		ToolID:            "get_public_ip",
		Metadata:          map[string]string{"base_url": baseURL},
	}
}
