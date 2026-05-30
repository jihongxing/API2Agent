package adapters

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"

	"api2agent/services/data-plane/internal/credentials"
	"api2agent/services/data-plane/internal/snapshots"
)

type HttpbinIPAdapter struct {
	Client *http.Client
}

func (a HttpbinIPAdapter) Call(ctx context.Context, provider snapshots.ProviderCandidate, input map[string]any, credentialPatch credentials.CredentialPatch) (Result, error) {
	client := a.Client
	if client == nil {
		client = http.DefaultClient
	}
	baseURL := provider.Metadata["base_url"]
	if baseURL == "" {
		baseURL = "https://httpbin.org/ip"
	}
	endpoint, err := url.Parse(baseURL)
	if err != nil {
		return Result{}, fmt.Errorf("parse httpbin base_url: %w", err)
	}
	query := endpoint.Query()
	for key, value := range credentialPatch.Query {
		query.Set(key, value)
	}
	endpoint.RawQuery = query.Encode()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint.String(), nil)
	if err != nil {
		return Result{}, err
	}
	for key, value := range credentialPatch.Headers {
		req.Header.Set(key, value)
	}
	resp, err := client.Do(req)
	if err != nil {
		return Result{}, err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return Result{StatusCode: resp.StatusCode, Method: http.MethodGet, Path: endpoint.Path}, fmt.Errorf("httpbin status %d", resp.StatusCode)
	}
	var payload struct {
		Origin string `json:"origin"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return Result{StatusCode: resp.StatusCode, Method: http.MethodGet, Path: endpoint.Path}, err
	}
	ip := strings.TrimSpace(payload.Origin)
	if ip == "" {
		return Result{StatusCode: resp.StatusCode, Method: http.MethodGet, Path: endpoint.Path}, fmt.Errorf("httpbin response missing origin")
	}
	return Result{
		Output:     map[string]any{"ip": ip},
		StatusCode: resp.StatusCode,
		Method:     http.MethodGet,
		Path:       endpoint.Path,
	}, nil
}
