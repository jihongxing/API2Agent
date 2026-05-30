package httpapi

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"api2agent/services/control-plane/internal/registry"
)

type Handler struct {
	Store           registry.Store
	RegistryStore   string
	RegistrySource  string
	DistributionDir string
	AdminToken      string
	Now             func() time.Time
}

type HealthResponse struct {
	Status          string `json:"status"`
	Service         string `json:"service"`
	SchemaVersion   string `json:"schema_version"`
	RegistryStore   string `json:"registry_store,omitempty"`
	RegistrySource  string `json:"registry_source,omitempty"`
	DistributionDir string `json:"distribution_dir,omitempty"`
}

type ErrorResponse struct {
	Error ErrorRecord `json:"error"`
}

type ErrorRecord struct {
	ErrorType  string `json:"error_type"`
	ErrorScope string `json:"error_scope"`
	Message    string `json:"message"`
	Retryable  bool   `json:"retryable"`
}

type RegistryValidationResponse struct {
	Valid               bool                            `json:"valid"`
	RegistryStore       string                          `json:"registry_store"`
	RegistrySource      string                          `json:"registry_source,omitempty"`
	RegistryFingerprint string                          `json:"registry_fingerprint"`
	Validation          registry.ExportValidationReport `json:"validation"`
}

type ExportArtifactRequest struct {
	OutputDir string `json:"output_dir"`
}

type ExportArtifactResponse struct {
	ArtifactDir string                          `json:"artifact_dir"`
	Manifest    registry.ExportArtifactManifest `json:"manifest"`
}

type DistributionCurrentResponse struct {
	DistributionDir string                               `json:"distribution_dir"`
	Pointer         registry.SnapshotDistributionPointer `json:"pointer"`
}

func (h Handler) Register(mux *http.ServeMux) {
	mux.HandleFunc("/healthz", h.Healthz)
	mux.HandleFunc("/v1/admin/registry/validate", h.ValidateRegistry)
	mux.HandleFunc("/v1/admin/snapshots/export-artifact", h.ExportArtifact)
	mux.HandleFunc("/v1/admin/distribution/current", h.DistributionCurrent)
}

func (h Handler) Healthz(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "INVALID_REQUEST", "caller", "method not allowed", false)
		return
	}
	writeJSON(w, http.StatusOK, HealthResponse{
		Status:          "ok",
		Service:         "api2agent-control-plane",
		SchemaVersion:   registry.ProtocolSchemaVersion,
		RegistryStore:   h.registryStore(),
		RegistrySource:  h.RegistrySource,
		DistributionDir: h.DistributionDir,
	})
}

func (h Handler) ValidateRegistry(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "INVALID_REQUEST", "caller", "method not allowed", false)
		return
	}
	if !h.authorized(r) {
		writeError(w, http.StatusUnauthorized, "AUTH_ERROR", "caller", "invalid control plane admin token", false)
		return
	}
	reg, err := h.loadRegistry(r.Context())
	if err != nil {
		writeError(w, http.StatusBadRequest, "REGISTRY_INVALID", "caller", err.Error(), false)
		return
	}
	fingerprint, err := reg.Fingerprint()
	if err != nil {
		writeError(w, http.StatusBadRequest, "REGISTRY_INVALID", "caller", err.Error(), false)
		return
	}
	writeJSON(w, http.StatusOK, RegistryValidationResponse{
		Valid:               true,
		RegistryStore:       h.registryStore(),
		RegistrySource:      h.RegistrySource,
		RegistryFingerprint: fingerprint,
		Validation:          validationReport(reg),
	})
}

func (h Handler) ExportArtifact(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "INVALID_REQUEST", "caller", "method not allowed", false)
		return
	}
	if !h.authorized(r) {
		writeError(w, http.StatusUnauthorized, "AUTH_ERROR", "caller", "invalid control plane admin token", false)
		return
	}
	var req ExportArtifactRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "caller", "invalid json body", false)
		return
	}
	if strings.TrimSpace(req.OutputDir) == "" {
		writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "caller", "output_dir is required", false)
		return
	}
	reg, err := h.loadRegistry(r.Context())
	if err != nil {
		writeError(w, http.StatusBadRequest, "REGISTRY_INVALID", "caller", err.Error(), false)
		return
	}
	snapshot, manifest, err := reg.ExportArtifact(h.now(), h.registryStore(), h.RegistrySource)
	if err != nil {
		writeError(w, http.StatusBadRequest, "REGISTRY_INVALID", "caller", err.Error(), false)
		return
	}
	if err := registry.WriteArtifactDir(req.OutputDir, snapshot, manifest); err != nil {
		writeError(w, http.StatusInternalServerError, "ARTIFACT_EXPORT_FAILED", "platform", err.Error(), true)
		return
	}
	writeJSON(w, http.StatusCreated, ExportArtifactResponse{
		ArtifactDir: req.OutputDir,
		Manifest:    manifest,
	})
}

func (h Handler) DistributionCurrent(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "INVALID_REQUEST", "caller", "method not allowed", false)
		return
	}
	if !h.authorized(r) {
		writeError(w, http.StatusUnauthorized, "AUTH_ERROR", "caller", "invalid control plane admin token", false)
		return
	}
	if strings.TrimSpace(h.DistributionDir) == "" {
		writeError(w, http.StatusConflict, "DISTRIBUTION_NOT_CONFIGURED", "platform", "distribution dir is not configured", false)
		return
	}
	currentPath := filepath.Join(h.DistributionDir, "current.json")
	if _, err := os.Stat(currentPath); err != nil {
		if errors.Is(err, os.ErrNotExist) {
			writeError(w, http.StatusNotFound, "DISTRIBUTION_POINTER_NOT_FOUND", "platform", "distribution current.json was not found", true)
			return
		}
		writeError(w, http.StatusInternalServerError, "DISTRIBUTION_READ_FAILED", "platform", err.Error(), true)
		return
	}
	pointer, err := registry.ReadDistributionPointerFile(currentPath)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "DISTRIBUTION_READ_FAILED", "platform", err.Error(), true)
		return
	}
	writeJSON(w, http.StatusOK, DistributionCurrentResponse{
		DistributionDir: h.DistributionDir,
		Pointer:         pointer,
	})
}

func (h Handler) loadRegistry(ctx context.Context) (*registry.Registry, error) {
	if h.Store == nil {
		return nil, fmt.Errorf("registry store is not configured")
	}
	return h.Store.Load(ctx)
}

func (h Handler) registryStore() string {
	if h.RegistryStore == "" {
		return "file"
	}
	return h.RegistryStore
}

func (h Handler) now() time.Time {
	if h.Now != nil {
		return h.Now().UTC()
	}
	return time.Now().UTC()
}

func (h Handler) authorized(r *http.Request) bool {
	if h.AdminToken == "" {
		return false
	}
	const prefix = "Bearer "
	header := r.Header.Get("Authorization")
	if !strings.HasPrefix(header, prefix) {
		return false
	}
	return strings.TrimSpace(strings.TrimPrefix(header, prefix)) == h.AdminToken
}

func validationReport(reg *registry.Registry) registry.ExportValidationReport {
	activeProviders := 0
	for _, provider := range reg.Providers {
		if provider.Status != "disabled" {
			activeProviders++
		}
	}
	return registry.ExportValidationReport{
		Valid:                   true,
		ProjectCount:            len(reg.Projects),
		APIKeyCount:             len(reg.APIKeys),
		CapabilityCount:         len(reg.Capabilities),
		ProviderCount:           len(reg.Providers),
		ActiveProviderCount:     activeProviders,
		CredentialMetadataCount: len(reg.CredentialMetadata),
	}
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeError(w http.ResponseWriter, status int, errorType string, scope string, message string, retryable bool) {
	writeJSON(w, status, ErrorResponse{
		Error: ErrorRecord{
			ErrorType:  errorType,
			ErrorScope: scope,
			Message:    message,
			Retryable:  retryable,
		},
	})
}
