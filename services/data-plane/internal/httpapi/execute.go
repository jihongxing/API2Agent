package httpapi

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"

	"api2agent/services/data-plane/internal/adapters"
	"api2agent/services/data-plane/internal/credentials"
	"api2agent/services/data-plane/internal/events"
	"api2agent/services/data-plane/internal/protocol"
	"api2agent/services/data-plane/internal/routing"
	"api2agent/services/data-plane/internal/snapshots"
)

type Handler struct {
	Snapshot   *snapshots.Snapshot
	Adapters   *adapters.Registry
	Events     events.Writer
	ProjectKey string
}

type ExecuteRequest struct {
	ProjectID         string                            `json:"project_id"`
	CapabilityID      string                            `json:"capability_id"`
	CapabilityVersion string                            `json:"capability_version"`
	Input             map[string]any                    `json:"input"`
	ExecutionMode     string                            `json:"execution_mode"`
	ClientRegion      *string                           `json:"client_region"`
	TimeoutBudgetMS   int                               `json:"timeout_budget_ms"`
	Credential        *credentials.CredentialDefinition `json:"credential"`
}

type ExecuteResponse struct {
	RequestID         string                `json:"request_id"`
	RoutingDecisionID string                `json:"routing_decision_id"`
	UsageEventID      string                `json:"usage_event_id"`
	Success           bool                  `json:"success"`
	Output            map[string]any        `json:"output,omitempty"`
	Error             *protocol.ErrorRecord `json:"error,omitempty"`
}

type HealthResponse struct {
	Status            string     `json:"status"`
	SchemaVersion     string     `json:"schema_version"`
	SnapshotVersion   string     `json:"snapshot_version,omitempty"`
	SnapshotFetchedAt *time.Time `json:"snapshot_fetched_at,omitempty"`
	SnapshotTTL       string     `json:"snapshot_ttl,omitempty"`
	SnapshotExpiresAt *time.Time `json:"snapshot_expires_at,omitempty"`
	SnapshotExpired   *bool      `json:"snapshot_expired,omitempty"`
	SnapshotSource    string     `json:"snapshot_source,omitempty"`
}

func (h Handler) Register(mux *http.ServeMux) {
	mux.HandleFunc("/v1/execute", h.Execute)
	mux.HandleFunc("/healthz", h.Healthz)
}

func (h Handler) Healthz(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "INVALID_REQUEST", "caller", "method not allowed")
		return
	}
	response := HealthResponse{
		Status:        "ok",
		SchemaVersion: protocol.SchemaVersion,
	}
	if h.Snapshot == nil {
		response.Status = "degraded"
		writeJSON(w, http.StatusOK, response)
		return
	}
	response.SnapshotVersion = h.Snapshot.SnapshotVersion
	response.SnapshotFetchedAt = &h.Snapshot.SnapshotFetchedAt
	response.SnapshotTTL = h.Snapshot.SnapshotTTL
	response.SnapshotSource = h.Snapshot.SnapshotSource
	if expiresAt, err := h.Snapshot.ExpiresAt(); err == nil {
		response.SnapshotExpiresAt = expiresAt
	}
	if expired, err := h.Snapshot.IsExpired(time.Now().UTC()); err == nil {
		response.SnapshotExpired = &expired
		if expired {
			response.Status = "degraded"
		}
	} else {
		response.Status = "degraded"
	}
	writeJSON(w, http.StatusOK, response)
}

func (h Handler) Execute(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "INVALID_REQUEST", "caller", "method not allowed")
		return
	}
	if h.ProjectKey != "" && !validBearer(r.Header.Get("Authorization"), h.ProjectKey) {
		writeError(w, http.StatusUnauthorized, "AUTH_ERROR", "caller", "invalid api2agent project key")
		return
	}

	var req ExecuteRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "caller", "invalid json body")
		return
	}
	if req.ProjectID == "" {
		req.ProjectID = "local"
	}
	if req.CapabilityVersion == "" {
		req.CapabilityVersion = "0.1-migrated"
	}
	if req.ExecutionMode == "" {
		req.ExecutionMode = "proxy"
	}
	if req.TimeoutBudgetMS <= 0 {
		req.TimeoutBudgetMS = 5000
	}
	if req.Input == nil {
		req.Input = map[string]any{}
	}
	if req.CapabilityID == "" {
		writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "caller", "capability_id is required")
		return
	}
	if h.Snapshot == nil || h.Adapters == nil || h.Events == nil {
		writeError(w, http.StatusInternalServerError, "PROVIDER_ERROR", "platform", "handler is not initialized")
		return
	}

	requestStartedAt := time.Now()
	requestDeadline := requestStartedAt.Add(time.Duration(req.TimeoutBudgetMS) * time.Millisecond)
	identity := protocol.IdentityRef{ProjectID: req.ProjectID}
	requestID := routing.NewID("req")
	now := time.Now().UTC()
	requestContext := protocol.RequestContext{
		ID:                requestID,
		SchemaVersion:     protocol.SchemaVersion,
		Identity:          identity,
		CapabilityID:      req.CapabilityID,
		CapabilityVersion: req.CapabilityVersion,
		ExecutionMode:     req.ExecutionMode,
		ClientRegion:      req.ClientRegion,
		CreatedAt:         now,
	}
	if !h.writeEvent(w, r.Context(), "request_context", requestContext) {
		return
	}
	if err := h.checkSnapshotFreshness(time.Now().UTC()); err != nil {
		h.writeFailedDecision(w, r.Context(), requestContext, nil, snapshotFreshnessError(err), http.StatusServiceUnavailable)
		return
	}

	decisionResult, err := routing.Decide(routing.DecisionInput{
		RequestID:         requestID,
		Identity:          identity,
		CapabilityID:      req.CapabilityID,
		ClientRegion:      req.ClientRegion,
		Snapshot:          h.Snapshot,
		ExecutionBudgetMS: req.TimeoutBudgetMS,
	})
	if err != nil {
		h.writeFailedDecision(w, r.Context(), requestContext, nil, errorRecord("NO_PROVIDER", "platform", err.Error(), false), http.StatusBadGateway)
		return
	}
	if !h.writeEvent(w, r.Context(), "routing_decision", decisionResult.Decision) {
		return
	}

	routeID := decisionResult.Decision.ID
	attempts := providersForAttempts(decisionResult)
	maxAttempts := maxAttempts(decisionResult.Decision.FailoverPolicy, len(attempts))
	var usageIDs []string
	var selectedProviderID *string
	var selectedProviderRegion *string
	var finalUsageID string
	var finalOutput map[string]any
	var finalError *protocol.ErrorRecord
	success := false
	timeoutBudgetExhausted := false

	for attemptIndex, provider := range attempts[:maxAttempts] {
		remainingBudget := time.Until(requestDeadline)
		if remainingBudget <= 0 {
			timeoutBudgetExhausted = true
			if finalError == nil {
				finalError = errorRecord("TIMEOUT", "platform", "request timeout budget exhausted before provider attempt", true)
			}
			break
		}
		attemptTimeoutBudgetMS := durationMillisecondsCeil(remainingBudget)
		providerRegion := selectedRegionForProvider(req.ClientRegion, provider)
		resolvedCredential := credentials.NewLocalResolver().Resolve(credentials.CredentialResolutionRequest{
			ProjectID:    req.ProjectID,
			CapabilityID: req.CapabilityID,
			ProviderID:   provider.ProviderID,
			ToolID:       provider.ToolID,
			Credential:   req.Credential,
		})
		adapter, ok := h.Adapters.Get(provider.ProviderID)
		var result adapters.Result
		var callErr error
		if !resolvedCredential.Resolved {
			callErr = errors.New(resolvedCredential.ErrorMessage)
		} else if !ok {
			callErr = errors.New("adapter not registered")
		} else {
			execCtx, cancel := context.WithTimeout(r.Context(), remainingBudget)
			start := time.Now()
			result, callErr = adapter.Call(execCtx, provider, req.Input, resolvedCredential.InjectionPatch)
			cancel()
			result.LatencyMS = float64(time.Since(start).Microseconds()) / 1000
		}

		statusCode := result.StatusCode
		if statusCode == 0 && callErr == nil {
			statusCode = http.StatusOK
		}
		attemptSuccess := callErr == nil
		var errRecord *protocol.ErrorRecord
		if callErr != nil {
			if !resolvedCredential.Resolved {
				errRecord = errorRecord(resolvedCredential.ErrorType, "platform", resolvedCredential.ErrorMessage, false)
			} else if !ok {
				errRecord = errorRecord("NO_PROVIDER", "platform", callErr.Error(), false)
			} else {
				errRecord = mapAdapterError(callErr)
			}
		}

		usageID := routing.NewID("usage")
		finalUsageID = usageID
		usageIDs = append(usageIDs, usageID)
		method := result.Method
		path := result.Path
		costSource := "estimated"
		estimatedCost := provider.EstimatedCost
		latencyMS := result.LatencyMS
		latency := protocol.LatencyProfile{LatencyMS: &latencyMS, LatencyRegion: req.ClientRegion}
		requestMetadata := map[string]any{
			"snapshot_version":            snapshotVersion(h.Snapshot),
			"execution_timeout_budget_ms": req.TimeoutBudgetMS,
			"total_timeout_budget_ms":     req.TimeoutBudgetMS,
			"attempt_timeout_budget_ms":   attemptTimeoutBudgetMS,
			"remaining_timeout_budget_ms": attemptTimeoutBudgetMS,
			"timeout_budget_policy":       "total_deadline",
			"attempt_timeout_policy":      attemptTimeoutPolicy(decisionResult.Decision.FailoverPolicy),
			"attempt_index":               attemptIndex + 1,
			"max_attempts":                maxAttempts,
		}
		if req.Credential != nil || resolvedCredential.CredentialReference != "none" {
			requestMetadata["credential"] = resolvedCredential.RedactedMetadata
		}
		usage := protocol.UsageEvent{
			ID:                usageID,
			SchemaVersion:     protocol.SchemaVersion,
			RequestID:         requestID,
			RoutingDecisionID: &routeID,
			ExecutionMode:     req.ExecutionMode,
			Identity:          identity,
			CapabilityID:      req.CapabilityID,
			CapabilityVersion: req.CapabilityVersion,
			ProviderID:        provider.ProviderID,
			ProviderVersion:   provider.ProviderVersion,
			MappingVersion:    provider.MappingVersion,
			ToolID:            provider.ToolID,
			Method:            &method,
			Path:              &path,
			StatusCode:        &statusCode,
			Success:           attemptSuccess,
			Latency:           latency,
			Topology: protocol.NetworkTopology{
				ClientRegion:           req.ClientRegion,
				SelectedProviderRegion: decisionResult.Decision.SelectedProviderRegion,
				ProviderRegion:         providerRegion,
			},
			Cost:                protocol.CostProfile{EstimatedCost: &estimatedCost, CostSource: &costSource},
			Error:               errRecord,
			RequestMetadata:     requestMetadata,
			CredentialReference: protocolCredentialReference(req.Credential, resolvedCredential),
			CreatedAt:           time.Now().UTC(),
		}
		if !h.writeEvent(w, r.Context(), "usage_event", &usage) {
			return
		}

		finalError = errRecord
		if attemptSuccess {
			success = true
			finalOutput = result.Output
			providerID := provider.ID
			selectedProviderID = &providerID
			selectedProviderRegion = providerRegion
			break
		}
		if !shouldFailover(decisionResult.Decision.FailoverPolicy, errRecord, statusCode) {
			break
		}
		if time.Until(requestDeadline) <= 0 {
			timeoutBudgetExhausted = true
			break
		}
	}

	outcome := "success"
	if !success {
		outcome = "failure"
	}
	decisionLog := protocol.DecisionLog{
		ID:                routing.NewID("decision_log"),
		SchemaVersion:     protocol.SchemaVersion,
		RequestID:         requestID,
		RoutingDecisionID: &routeID,
		Identity:          identity,
		CapabilityID:      req.CapabilityID,
		RoutingStrategy:   decisionResult.Decision.Strategy,
		RoutingContext: map[string]any{
			"snapshot_version":            snapshotVersion(h.Snapshot),
			"routing_mode":                decisionResult.Decision.RoutingMode,
			"attempt_count":               len(usageIDs),
			"total_timeout_budget_ms":     req.TimeoutBudgetMS,
			"timeout_budget_policy":       "total_deadline",
			"timeout_budget_exhausted":    timeoutBudgetExhausted,
			"remaining_timeout_budget_ms": durationMillisecondsCeil(time.Until(requestDeadline)),
			"attempt_timeout_policy":      attemptTimeoutPolicy(decisionResult.Decision.FailoverPolicy),
			"execution_timeout_budget_ms": req.TimeoutBudgetMS,
		},
		SelectedProviderID:     selectedProviderID,
		SelectedProviderRegion: selectedProviderRegion,
		Outcome:                outcome,
		UsageEventIDs:          usageIDs,
		CreatedAt:              time.Now().UTC(),
	}
	if !h.writeEvent(w, r.Context(), "decision_log", &decisionLog) {
		return
	}

	if !success {
		writeJSON(w, http.StatusBadGateway, ExecuteResponse{
			RequestID:         requestID,
			RoutingDecisionID: routeID,
			UsageEventID:      finalUsageID,
			Success:           false,
			Error:             finalError,
		})
		return
	}
	writeJSON(w, http.StatusOK, ExecuteResponse{
		RequestID:         requestID,
		RoutingDecisionID: routeID,
		UsageEventID:      finalUsageID,
		Success:           true,
		Output:            finalOutput,
	})
}

func (h Handler) writeFailedDecision(w http.ResponseWriter, ctx context.Context, request protocol.RequestContext, decision *protocol.RoutingDecision, record *protocol.ErrorRecord, status int) {
	var routeID string
	if decision != nil {
		routeID = decision.ID
	}
	routingContext := map[string]any{"snapshot_version": snapshotVersion(h.Snapshot)}
	if record != nil {
		if record.ErrorType != nil {
			routingContext["error_type"] = *record.ErrorType
		}
		if record.ErrorScope != nil {
			routingContext["error_scope"] = *record.ErrorScope
		}
	}
	decisionLog := protocol.DecisionLog{
		ID:              routing.NewID("decision_log"),
		SchemaVersion:   protocol.SchemaVersion,
		RequestID:       request.ID,
		Identity:        request.Identity,
		CapabilityID:    request.CapabilityID,
		RoutingStrategy: "none",
		RoutingContext:  routingContext,
		Outcome:         "failure",
		UsageEventIDs:   []string{},
		CreatedAt:       time.Now().UTC(),
	}
	if decision != nil {
		decisionLog.RoutingDecisionID = &decision.ID
	}
	if !h.writeEvent(w, ctx, "decision_log", &decisionLog) {
		return
	}
	writeJSON(w, status, ExecuteResponse{
		RequestID:         request.ID,
		RoutingDecisionID: routeID,
		Success:           false,
		Error:             record,
	})
}

func (h Handler) checkSnapshotFreshness(now time.Time) error {
	if h.Snapshot == nil {
		return errors.New("snapshot is required")
	}
	expired, err := h.Snapshot.IsExpired(now)
	if err != nil {
		return err
	}
	if expired {
		expiresAt, expiresErr := h.Snapshot.ExpiresAt()
		if expiresErr != nil {
			return expiresErr
		}
		if expiresAt != nil {
			return fmt.Errorf("snapshot %q expired at %s", h.Snapshot.SnapshotVersion, expiresAt.Format(time.RFC3339))
		}
		return fmt.Errorf("snapshot %q expired", h.Snapshot.SnapshotVersion)
	}
	return nil
}

func snapshotFreshnessError(err error) *protocol.ErrorRecord {
	message := err.Error()
	errorType := "SNAPSHOT_EXPIRED"
	if strings.Contains(message, "parse snapshot_ttl") {
		errorType = "SNAPSHOT_INVALID"
	}
	return errorRecord(errorType, "platform", message, false)
}

func (h Handler) writeEvent(w http.ResponseWriter, ctx context.Context, eventType string, record any) bool {
	if _, err := h.Events.Write(ctx, eventType, record); err != nil {
		writeJSON(w, http.StatusInternalServerError, ExecuteResponse{
			Success: false,
			Error:   errorRecord("EVENT_WRITE_FAILED", "platform", fmt.Sprintf("write %s event: %v", eventType, err), false),
		})
		return false
	}
	return true
}

func validBearer(header, expected string) bool {
	const prefix = "Bearer "
	if !strings.HasPrefix(header, prefix) {
		return false
	}
	return strings.TrimSpace(strings.TrimPrefix(header, prefix)) == expected
}

func snapshotVersion(snapshot *snapshots.Snapshot) string {
	if snapshot == nil {
		return ""
	}
	return snapshot.SnapshotVersion
}

func protocolCredentialReference(credential *credentials.CredentialDefinition, resolved credentials.ResolvedCredential) *protocol.CredentialReference {
	if credential == nil && resolved.CredentialReference == "none" {
		return nil
	}
	reference := resolved.CredentialReference
	credentialID := ""
	ownerType := ""
	ownerID := ""
	providerID := ""
	authType := ""
	injectionMode := ""
	source := ""
	status := ""
	if credential != nil {
		credentialID = credential.CredentialID
		ownerType = credential.OwnerType
		ownerID = credential.OwnerID
		providerID = credential.ProviderID
		authType = credential.AuthType
		injectionMode = credential.InjectionMode
		source = credential.Source
		status = credential.Status
	}
	return &protocol.CredentialReference{
		CredentialReference: stringPtr(reference),
		CredentialID:        optionalStringPtr(credentialID),
		OwnerType:           optionalStringPtr(ownerType),
		OwnerID:             optionalStringPtr(ownerID),
		ProviderID:          optionalStringPtr(providerID),
		AuthType:            optionalStringPtr(authType),
		InjectionMode:       optionalStringPtr(injectionMode),
		Source:              optionalStringPtr(source),
		ResolutionStrategy:  stringPtr("per_request"),
		Status:              optionalStringPtr(status),
	}
}

func stringPtr(value string) *string {
	return &value
}

func optionalStringPtr(value string) *string {
	if value == "" {
		return nil
	}
	return &value
}

func providersForAttempts(result routing.DecisionResult) []snapshots.ProviderCandidate {
	if len(result.Providers) > 0 {
		return result.Providers
	}
	return []snapshots.ProviderCandidate{result.Provider}
}

func maxAttempts(policy *protocol.FailoverPolicy, providerCount int) int {
	if providerCount <= 0 {
		return 0
	}
	if policy == nil || !policy.Enabled || policy.MaxAttempts <= 0 {
		return 1
	}
	if policy.MaxAttempts > providerCount {
		return providerCount
	}
	return policy.MaxAttempts
}

func attemptTimeoutPolicy(policy *protocol.FailoverPolicy) string {
	if policy == nil || policy.AttemptTimeoutPolicy == "" {
		return "fixed"
	}
	return policy.AttemptTimeoutPolicy
}

func shouldFailover(policy *protocol.FailoverPolicy, record *protocol.ErrorRecord, statusCode int) bool {
	if policy == nil || !policy.Enabled {
		return false
	}
	if record != nil && record.ErrorType != nil {
		for _, errorType := range policy.RetryOnErrorTypes {
			if errorType == *record.ErrorType {
				return true
			}
		}
	}
	for _, retryStatus := range policy.RetryOnStatusCodes {
		if retryStatus == statusCode {
			return true
		}
	}
	return false
}

func selectedRegionForProvider(clientRegion *string, provider snapshots.ProviderCandidate) *string {
	if clientRegion != nil {
		for _, region := range provider.Regions {
			if region == *clientRegion {
				value := region
				return &value
			}
		}
	}
	for _, region := range provider.Regions {
		if region == "global" {
			value := region
			return &value
		}
	}
	if provider.GeoAffinity == "global" {
		value := "global"
		return &value
	}
	if len(provider.Regions) > 0 {
		value := provider.Regions[0]
		return &value
	}
	return nil
}

func durationMillisecondsCeil(duration time.Duration) int {
	if duration <= 0 {
		return 0
	}
	milliseconds := int(duration / time.Millisecond)
	if duration%time.Millisecond != 0 {
		milliseconds++
	}
	if milliseconds == 0 {
		return 1
	}
	return milliseconds
}

func mapAdapterError(err error) *protocol.ErrorRecord {
	if errors.Is(err, context.DeadlineExceeded) {
		return errorRecord("TIMEOUT", "provider", err.Error(), true)
	}
	return errorRecord("PROVIDER_ERROR", "provider", err.Error(), true)
}

func errorRecord(errorType, scope, message string, retryable bool) *protocol.ErrorRecord {
	return &protocol.ErrorRecord{
		ErrorType:  &errorType,
		ErrorScope: &scope,
		Message:    &message,
		Retryable:  &retryable,
	}
}

func writeError(w http.ResponseWriter, status int, errorType, scope, message string) {
	writeJSON(w, status, ExecuteResponse{Success: false, Error: errorRecord(errorType, scope, message, false)})
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}
