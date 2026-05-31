package httpapi

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"api2agent/services/control-plane/internal/registry"
)

type Handler struct {
	Store           registry.Store
	AuditSink       registry.PersistentAuditSink
	ImportReplacer  RegistryImportReplacer
	RegistryStore   string
	RegistrySource  string
	DistributionDir string
	AdminToken      string
	Now             func() time.Time
}

const importReplaceMaxBodyBytes int64 = 2 * 1024 * 1024

type RegistryImportReplacer interface {
	ReplacePersistentRegistry(ctx context.Context, reg registry.Registry, opts registry.ImportReplaceOptions) (registry.ImportReplaceResult, error)
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

type ImportReplaceRequest struct {
	Registry json.RawMessage `json:"registry"`
	Source   string          `json:"source,omitempty"`
	DryRun   bool            `json:"dry_run,omitempty"`
}

type ImportReplaceResponse struct {
	RegistryStore               string                       `json:"registry_store"`
	RegistryFingerprint         string                       `json:"registry_fingerprint"`
	PreviousRegistryFingerprint string                       `json:"previous_registry_fingerprint,omitempty"`
	SnapshotVersion             string                       `json:"snapshot_version"`
	Noop                        bool                         `json:"noop"`
	Counts                      registry.ImportReplaceCounts `json:"counts"`
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

type PublishArtifactRequest struct {
	ArtifactDir string `json:"artifact_dir"`
}

type PublishArtifactResponse struct {
	DistributionDir string                               `json:"distribution_dir"`
	Pointer         registry.SnapshotDistributionPointer `json:"pointer"`
}

func (h Handler) Register(mux *http.ServeMux) {
	mux.HandleFunc("/healthz", h.Healthz)
	mux.HandleFunc("/v1/admin/registry/validate", h.ValidateRegistry)
	mux.HandleFunc("/v1/admin/registry/import-replace", h.ImportReplaceRegistry)
	mux.HandleFunc("/v1/admin/snapshots/export-artifact", h.ExportArtifact)
	mux.HandleFunc("/v1/admin/distribution/publish", h.PublishArtifact)
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
		errorType, _, _, _ := h.registryLoadFailure()
		h.recordAdminAuditFailure(r.Context(), r, "registry.validate", "registry", h.RegistrySource, errorType)
		h.writeRegistryLoadError(w, err)
		return
	}
	fingerprint, err := reg.Fingerprint()
	if err != nil {
		h.recordAdminAuditFailure(r.Context(), r, "registry.validate", "registry", h.RegistrySource, "REGISTRY_INVALID")
		writeError(w, http.StatusBadRequest, "REGISTRY_INVALID", "caller", err.Error(), false)
		return
	}
	if err := h.recordAdminAuditSuccess(r.Context(), r, "registry.validate", "registry", fingerprint, map[string]string{
		"registry_fingerprint": fingerprint,
	}); err != nil {
		writeError(w, http.StatusInternalServerError, "AUDIT_WRITE_FAILED", "platform", err.Error(), true)
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

func (h Handler) ImportReplaceRegistry(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "INVALID_REQUEST", "caller", "method not allowed", false)
		return
	}
	if !h.authorized(r) {
		writeError(w, http.StatusUnauthorized, "AUTH_ERROR", "caller", "invalid control plane admin token", false)
		return
	}
	requestID := strings.TrimSpace(r.Header.Get("X-Request-ID"))
	if requestID == "" {
		writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "caller", "X-Request-ID is required", false)
		return
	}
	idempotencyKey := strings.TrimSpace(r.Header.Get("Idempotency-Key"))
	if idempotencyKey == "" {
		writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "caller", "Idempotency-Key is required", false)
		return
	}
	if h.registryStore() != "postgres" || h.ImportReplacer == nil {
		writeError(w, http.StatusConflict, "REGISTRY_MUTATION_UNAVAILABLE", "platform", "registry import/replace requires postgres mutation mode", false)
		return
	}

	r.Body = http.MaxBytesReader(w, r.Body, importReplaceMaxBodyBytes)
	var req ImportReplaceRequest
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&req); err != nil {
		if requestBodyTooLarge(err) {
			writeError(w, http.StatusRequestEntityTooLarge, "REQUEST_BODY_TOO_LARGE", "caller", "request body exceeds 2 MiB limit", false)
			return
		}
		writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "caller", "invalid json body", false)
		return
	}
	if err := ensureSingleJSONDocument(decoder); err != nil {
		if requestBodyTooLarge(err) {
			writeError(w, http.StatusRequestEntityTooLarge, "REQUEST_BODY_TOO_LARGE", "caller", "request body exceeds 2 MiB limit", false)
			return
		}
		writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "caller", "invalid json body", false)
		return
	}
	if len(req.Registry) == 0 || strings.TrimSpace(string(req.Registry)) == "null" {
		writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "caller", "registry is required", false)
		return
	}
	if req.DryRun {
		writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "caller", "dry_run=true is reserved and not supported in v0", false)
		return
	}
	var incoming registry.Registry
	if err := json.Unmarshal(req.Registry, &incoming); err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "caller", "invalid registry json", false)
		return
	}
	source := strings.TrimSpace(req.Source)
	if source == "" {
		source = "admin_http_import"
	}
	actorID := strings.TrimSpace(r.Header.Get("X-Actor-ID"))
	if actorID == "" {
		actorID = "admin"
	}
	result, err := h.ImportReplacer.ReplacePersistentRegistry(r.Context(), incoming, registry.ImportReplaceOptions{
		ActorID:        actorID,
		RequestID:      requestID,
		IdempotencyKey: idempotencyKey,
		Source:         source,
	})
	if err != nil {
		h.writeRegistryMutationError(w, err)
		return
	}
	status := http.StatusCreated
	if result.Noop {
		status = http.StatusOK
	}
	writeJSON(w, status, ImportReplaceResponse{
		RegistryStore:               h.registryStore(),
		RegistryFingerprint:         result.RegistryFingerprint,
		PreviousRegistryFingerprint: result.PreviousRegistryFingerprint,
		SnapshotVersion:             result.SnapshotVersion,
		Noop:                        result.Noop,
		Counts:                      result.Counts,
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
		h.recordAdminAuditFailure(r.Context(), r, "snapshot.export_artifact", "snapshot_artifact", "", "INVALID_REQUEST")
		writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "caller", "invalid json body", false)
		return
	}
	if strings.TrimSpace(req.OutputDir) == "" {
		h.recordAdminAuditFailure(r.Context(), r, "snapshot.export_artifact", "snapshot_artifact", "", "INVALID_REQUEST")
		writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "caller", "output_dir is required", false)
		return
	}
	reg, err := h.loadRegistry(r.Context())
	if err != nil {
		errorType, _, _, _ := h.registryLoadFailure()
		h.recordAdminAuditFailure(r.Context(), r, "snapshot.export_artifact", "snapshot_artifact", req.OutputDir, errorType)
		h.writeRegistryLoadError(w, err)
		return
	}
	snapshot, manifest, err := reg.ExportArtifact(h.now(), h.registryStore(), h.RegistrySource)
	if err != nil {
		h.recordAdminAuditFailure(r.Context(), r, "snapshot.export_artifact", "snapshot_artifact", req.OutputDir, "REGISTRY_INVALID")
		writeError(w, http.StatusBadRequest, "REGISTRY_INVALID", "caller", err.Error(), false)
		return
	}
	if err := registry.WriteArtifactDir(req.OutputDir, snapshot, manifest); err != nil {
		h.recordAdminAuditFailure(r.Context(), r, "snapshot.export_artifact", "snapshot_artifact", manifest.SnapshotVersion, "ARTIFACT_EXPORT_FAILED")
		writeError(w, http.StatusInternalServerError, "ARTIFACT_EXPORT_FAILED", "platform", err.Error(), true)
		return
	}
	if err := h.recordRegistryRevision(r.Context(), snapshot); err != nil {
		writeError(w, http.StatusInternalServerError, "AUDIT_WRITE_FAILED", "platform", err.Error(), true)
		return
	}
	if err := h.recordAdminAuditSuccess(r.Context(), r, "snapshot.export_artifact", "snapshot_artifact", manifest.SnapshotVersion, map[string]string{
		"artifact_dir":         req.OutputDir,
		"registry_fingerprint": manifest.RegistryFingerprint,
		"snapshot_digest":      manifest.SnapshotDigest,
		"snapshot_version":     manifest.SnapshotVersion,
	}); err != nil {
		writeError(w, http.StatusInternalServerError, "AUDIT_WRITE_FAILED", "platform", err.Error(), true)
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
		h.recordAdminAuditFailure(r.Context(), r, "distribution.current.read", "distribution", h.DistributionDir, "DISTRIBUTION_NOT_CONFIGURED")
		writeError(w, http.StatusConflict, "DISTRIBUTION_NOT_CONFIGURED", "platform", "distribution dir is not configured", false)
		return
	}
	currentPath := filepath.Join(h.DistributionDir, "current.json")
	if _, err := os.Stat(currentPath); err != nil {
		if errors.Is(err, os.ErrNotExist) {
			h.recordAdminAuditFailure(r.Context(), r, "distribution.current.read", "distribution", currentPath, "DISTRIBUTION_POINTER_NOT_FOUND")
			writeError(w, http.StatusNotFound, "DISTRIBUTION_POINTER_NOT_FOUND", "platform", "distribution current.json was not found", true)
			return
		}
		h.recordAdminAuditFailure(r.Context(), r, "distribution.current.read", "distribution", currentPath, "DISTRIBUTION_READ_FAILED")
		writeError(w, http.StatusInternalServerError, "DISTRIBUTION_READ_FAILED", "platform", err.Error(), true)
		return
	}
	pointer, err := registry.ReadDistributionPointerFile(currentPath)
	if err != nil {
		h.recordAdminAuditFailure(r.Context(), r, "distribution.current.read", "distribution", currentPath, "DISTRIBUTION_READ_FAILED")
		writeError(w, http.StatusInternalServerError, "DISTRIBUTION_READ_FAILED", "platform", err.Error(), true)
		return
	}
	if err := h.recordAdminAuditSuccess(r.Context(), r, "distribution.current.read", "distribution", pointer.SnapshotVersion, map[string]string{
		"distribution_pointer": currentPath,
		"snapshot_version":     pointer.SnapshotVersion,
		"snapshot_digest":      pointer.SnapshotDigest,
	}); err != nil {
		writeError(w, http.StatusInternalServerError, "AUDIT_WRITE_FAILED", "platform", err.Error(), true)
		return
	}
	writeJSON(w, http.StatusOK, DistributionCurrentResponse{
		DistributionDir: h.DistributionDir,
		Pointer:         pointer,
	})
}

func (h Handler) PublishArtifact(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "INVALID_REQUEST", "caller", "method not allowed", false)
		return
	}
	if !h.authorized(r) {
		writeError(w, http.StatusUnauthorized, "AUTH_ERROR", "caller", "invalid control plane admin token", false)
		return
	}
	if strings.TrimSpace(h.DistributionDir) == "" {
		h.recordAdminAuditFailure(r.Context(), r, "distribution.publish", "snapshot_artifact", "", "DISTRIBUTION_NOT_CONFIGURED")
		writeError(w, http.StatusConflict, "DISTRIBUTION_NOT_CONFIGURED", "platform", "distribution dir is not configured", false)
		return
	}
	var req PublishArtifactRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.recordAdminAuditFailure(r.Context(), r, "distribution.publish", "snapshot_artifact", "", "INVALID_REQUEST")
		writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "caller", "invalid json body", false)
		return
	}
	if strings.TrimSpace(req.ArtifactDir) == "" {
		h.recordAdminAuditFailure(r.Context(), r, "distribution.publish", "snapshot_artifact", "", "INVALID_REQUEST")
		writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "caller", "artifact_dir is required", false)
		return
	}
	pointer, err := registry.PublishArtifactDir(req.ArtifactDir, h.DistributionDir, h.now())
	if err != nil {
		status := http.StatusBadRequest
		errorType := "DISTRIBUTION_PUBLISH_FAILED"
		retryable := false
		if strings.Contains(err.Error(), "already exists") {
			status = http.StatusConflict
			errorType = "DISTRIBUTION_ARTIFACT_EXISTS"
		}
		h.recordAdminAuditFailure(r.Context(), r, "distribution.publish", "snapshot_artifact", req.ArtifactDir, errorType)
		writeError(w, status, errorType, "platform", err.Error(), retryable)
		return
	}
	if err := h.recordArtifactPublication(r.Context(), pointer); err != nil {
		writeError(w, http.StatusInternalServerError, "AUDIT_WRITE_FAILED", "platform", err.Error(), true)
		return
	}
	if err := h.recordAdminAuditSuccess(r.Context(), r, "distribution.publish", "snapshot_artifact", pointer.SnapshotVersion, map[string]string{
		"artifact_dir":         pointer.ArtifactDir,
		"source_artifact_dir":  pointer.SourceArtifactDir,
		"registry_fingerprint": pointer.RegistryFingerprint,
		"snapshot_digest":      pointer.SnapshotDigest,
		"snapshot_version":     pointer.SnapshotVersion,
	}); err != nil {
		writeError(w, http.StatusInternalServerError, "AUDIT_WRITE_FAILED", "platform", err.Error(), true)
		return
	}
	writeJSON(w, http.StatusCreated, PublishArtifactResponse{
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

func (h Handler) writeRegistryLoadError(w http.ResponseWriter, err error) {
	errorType, scope, status, retryable := h.registryLoadFailure()
	writeError(w, status, errorType, scope, err.Error(), retryable)
}

func (h Handler) writeRegistryMutationError(w http.ResponseWriter, err error) {
	var mutationErr registry.RegistryMutationError
	if errors.As(err, &mutationErr) {
		status := http.StatusInternalServerError
		switch mutationErr.ErrorType {
		case "REGISTRY_MUTATION_INVALID":
			status = http.StatusBadRequest
		case "REGISTRY_MUTATION_CONFLICT":
			status = http.StatusConflict
		case "PERSISTENT_STORE_READ_FAILED", "PERSISTENT_STORE_WRITE_FAILED":
			status = http.StatusServiceUnavailable
		case "AUDIT_WRITE_FAILED":
			status = http.StatusInternalServerError
		}
		writeError(w, status, mutationErr.ErrorType, mutationErr.Scope, mutationErr.Error(), mutationErr.Retryable)
		return
	}
	writeError(w, http.StatusInternalServerError, "REGISTRY_MUTATION_FAILED", "platform", err.Error(), true)
}

func (h Handler) registryLoadFailure() (errorType string, scope string, status int, retryable bool) {
	if h.registryStore() == "postgres" {
		return "PERSISTENT_STORE_READ_FAILED", "platform", http.StatusServiceUnavailable, true
	}
	return "REGISTRY_INVALID", "caller", http.StatusBadRequest, false
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

func (h Handler) recordRegistryRevision(ctx context.Context, snapshot registry.RoutingSnapshot) error {
	if h.AuditSink == nil {
		return nil
	}
	return h.AuditSink.RecordRegistryRevision(ctx, registry.PersistentRegistryRevisionRow{
		RegistryFingerprint: snapshot.Metadata["registry_fingerprint"],
		SnapshotVersion:     snapshot.SnapshotVersion,
		SourceStore:         h.registryStore(),
		SourceRevision:      h.RegistrySource,
	})
}

func (h Handler) recordArtifactPublication(ctx context.Context, pointer registry.SnapshotDistributionPointer) error {
	if h.AuditSink == nil {
		return nil
	}
	return h.AuditSink.RecordArtifactPublication(ctx, registry.PersistentArtifactPublicationRow{
		SnapshotVersion:     pointer.SnapshotVersion,
		RegistryFingerprint: pointer.RegistryFingerprint,
		SnapshotDigest:      pointer.SnapshotDigest,
		ArtifactURI:         pointer.ArtifactDir,
		ManifestURI:         pointer.ManifestFile,
		DistributionURI:     filepath.Join(h.DistributionDir, "current.json"),
		Status:              "published",
	})
}

func (h Handler) recordAdminAuditSuccess(ctx context.Context, r *http.Request, action string, resourceType string, resourceID string, metadata map[string]string) error {
	return h.recordAdminAudit(ctx, r, action, resourceType, resourceID, "success", "", metadata)
}

func (h Handler) recordAdminAuditFailure(ctx context.Context, r *http.Request, action string, resourceType string, resourceID string, errorType string) {
	_ = h.recordAdminAudit(ctx, r, action, resourceType, resourceID, "failure", errorType, nil)
}

func (h Handler) recordAdminAudit(ctx context.Context, r *http.Request, action string, resourceType string, resourceID string, outcome string, errorType string, metadata map[string]string) error {
	if h.AuditSink == nil {
		return nil
	}
	return h.AuditSink.RecordAdminAuditEvent(ctx, registry.PersistentAdminAuditEventRow{
		ActorID:      "admin",
		Action:       action,
		ResourceType: resourceType,
		ResourceID:   resourceID,
		RequestID:    r.Header.Get("X-Request-ID"),
		Outcome:      outcome,
		ErrorType:    errorType,
		Metadata:     h.auditMetadata(metadata),
	})
}

func (h Handler) auditMetadata(extra map[string]string) map[string]string {
	metadata := map[string]string{
		"registry_store": h.registryStore(),
	}
	if h.RegistrySource != "" {
		metadata["registry_source"] = h.RegistrySource
	}
	if h.DistributionDir != "" {
		metadata["distribution_dir"] = h.DistributionDir
	}
	for key, value := range extra {
		metadata[key] = value
	}
	return metadata
}

func ensureSingleJSONDocument(decoder *json.Decoder) error {
	var extra any
	if err := decoder.Decode(&extra); err == io.EOF {
		return nil
	} else if err != nil {
		return err
	}
	return fmt.Errorf("multiple json documents")
}

func requestBodyTooLarge(err error) bool {
	return strings.Contains(err.Error(), "request body too large")
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
