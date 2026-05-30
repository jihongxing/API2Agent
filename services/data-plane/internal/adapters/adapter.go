package adapters

import (
	"context"

	"api2agent/services/data-plane/internal/credentials"
	"api2agent/services/data-plane/internal/snapshots"
)

type Result struct {
	Output     map[string]any
	StatusCode int
	Method     string
	Path       string
	LatencyMS  float64
}

type Adapter interface {
	Call(ctx context.Context, provider snapshots.ProviderCandidate, input map[string]any, credentialPatch credentials.CredentialPatch) (Result, error)
}

type Registry struct {
	adapters map[string]Adapter
}

func NewRegistry() *Registry {
	return &Registry{adapters: map[string]Adapter{}}
}

func (r *Registry) Register(providerID string, adapter Adapter) {
	r.adapters[providerID] = adapter
}

func (r *Registry) Get(providerID string) (Adapter, bool) {
	adapter, ok := r.adapters[providerID]
	return adapter, ok
}
