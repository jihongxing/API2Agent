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

type IpifyAdapter struct {
	Client *http.Client
}

func (a IpifyAdapter) Call(ctx context.Context, provider snapshots.ProviderCandidate, input map[string]any, credentialPatch credentials.CredentialPatch) (Result, error) {
	client := a.Client
	if client == nil {
		client = http.DefaultClient
	}
	baseURL := provider.Metadata["base_url"]
	if baseURL == "" {
		baseURL = "https://api.ipify.org"
	}
	endpoint, err := url.Parse(baseURL)
	if err != nil {
		return Result{}, fmt.Errorf("parse ipify base_url: %w", err)
	}
	query := endpoint.Query()
	query.Set("format", "json")
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
		return Result{StatusCode: resp.StatusCode, Method: http.MethodGet, Path: endpoint.Path}, fmt.Errorf("ipify status %d", resp.StatusCode)
	}
	var payload struct {
		IP string `json:"ip"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return Result{StatusCode: resp.StatusCode, Method: http.MethodGet, Path: endpoint.Path}, err
	}
	if strings.TrimSpace(payload.IP) == "" {
		return Result{StatusCode: resp.StatusCode, Method: http.MethodGet, Path: endpoint.Path}, fmt.Errorf("ipify response missing ip")
	}
	return Result{
		Output:     map[string]any{"ip": payload.IP},
		StatusCode: resp.StatusCode,
		Method:     http.MethodGet,
		Path:       endpoint.Path,
	}, nil
}
