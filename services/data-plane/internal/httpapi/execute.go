package httpapi

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strings"
	"time"

	"api2agent/services/data-plane/internal/adapters"
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
	ProjectID         string         `json:"project_id"`
	CapabilityID      string         `json:"capability_id"`
	CapabilityVersion string         `json:"capability_version"`
	Input             map[string]any `json:"input"`
	ExecutionMode     string         `json:"execution_mode"`
	ClientRegion      *string        `json:"client_region"`
	TimeoutBudgetMS   int            `json:"timeout_budget_ms"`
}

type ExecuteResponse struct {
	RequestID         string                `json:"request_id"`
	RoutingDecisionID string                `json:"routing_decision_id"`
	UsageEventID      string                `json:"usage_event_id"`
	Success           bool                  `json:"success"`
	Output            map[string]any        `json:"output,omitempty"`
	Error             *protocol.ErrorRecord `json:"error,omitempty"`
}

func (h Handler) Register(mux *http.ServeMux) {
	mux.HandleFunc("/v1/execute", h.Execute)
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
	_, _ = h.Events.Write(r.Context(), "request_context", requestContext)

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
	_, _ = h.Events.Write(r.Context(), "routing_decision", decisionResult.Decision)

	adapter, ok := h.Adapters.Get(decisionResult.Provider.ProviderID)
	if !ok {
		h.writeFailedDecision(w, r.Context(), requestContext, &decisionResult.Decision, errorRecord("NO_PROVIDER", "platform", "adapter not registered", false), http.StatusBadGateway)
		return
	}

	execCtx, cancel := context.WithTimeout(r.Context(), time.Duration(req.TimeoutBudgetMS)*time.Millisecond)
	defer cancel()
	start := time.Now()
	result, callErr := adapter.Call(execCtx, decisionResult.Provider, req.Input)
	latencyMS := float64(time.Since(start).Microseconds()) / 1000
	statusCode := result.StatusCode
	if statusCode == 0 && callErr == nil {
		statusCode = http.StatusOK
	}
	success := callErr == nil
	var errRecord *protocol.ErrorRecord
	if callErr != nil {
		errRecord = mapAdapterError(callErr)
	}

	usageID := routing.NewID("usage")
	routeID := decisionResult.Decision.ID
	method := result.Method
	path := result.Path
	costSource := "estimated"
	estimatedCost := decisionResult.Provider.EstimatedCost
	latency := protocol.LatencyProfile{LatencyMS: &latencyMS, LatencyRegion: req.ClientRegion}
	usage := protocol.UsageEvent{
		ID:                usageID,
		SchemaVersion:     protocol.SchemaVersion,
		RequestID:         requestID,
		RoutingDecisionID: &routeID,
		ExecutionMode:     req.ExecutionMode,
		Identity:          identity,
		CapabilityID:      req.CapabilityID,
		CapabilityVersion: req.CapabilityVersion,
		ProviderID:        decisionResult.Provider.ProviderID,
		ProviderVersion:   decisionResult.Provider.ProviderVersion,
		MappingVersion:    decisionResult.Provider.MappingVersion,
		ToolID:            decisionResult.Provider.ToolID,
		Method:            &method,
		Path:              &path,
		StatusCode:        &statusCode,
		Success:           success,
		Latency:           latency,
		Topology: protocol.NetworkTopology{
			ClientRegion:           req.ClientRegion,
			SelectedProviderRegion: decisionResult.Decision.SelectedProviderRegion,
			ProviderRegion:         decisionResult.Decision.SelectedProviderRegion,
		},
		Cost:  protocol.CostProfile{EstimatedCost: &estimatedCost, CostSource: &costSource},
		Error: errRecord,
		RequestMetadata: map[string]any{
			"snapshot_version":            h.Snapshot.SnapshotVersion,
			"execution_timeout_budget_ms": req.TimeoutBudgetMS,
			"attempt_timeout_policy":      "fixed",
		},
		CredentialReference: &protocol.CredentialReference{},
		CreatedAt:           time.Now().UTC(),
	}
	_, _ = h.Events.Write(r.Context(), "usage_event", &usage)

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
			"snapshot_version": h.Snapshot.SnapshotVersion,
			"routing_mode":     decisionResult.Decision.RoutingMode,
		},
		SelectedProviderID:     decisionResult.Decision.SelectedProviderID,
		SelectedProviderRegion: decisionResult.Decision.SelectedProviderRegion,
		Outcome:                outcome,
		UsageEventIDs:          []string{usageID},
		CreatedAt:              time.Now().UTC(),
	}
	_, _ = h.Events.Write(r.Context(), "decision_log", &decisionLog)

	if !success {
		writeJSON(w, http.StatusBadGateway, ExecuteResponse{
			RequestID:         requestID,
			RoutingDecisionID: routeID,
			UsageEventID:      usageID,
			Success:           false,
			Error:             errRecord,
		})
		return
	}
	writeJSON(w, http.StatusOK, ExecuteResponse{
		RequestID:         requestID,
		RoutingDecisionID: routeID,
		UsageEventID:      usageID,
		Success:           true,
		Output:            result.Output,
	})
}

func (h Handler) writeFailedDecision(w http.ResponseWriter, ctx context.Context, request protocol.RequestContext, decision *protocol.RoutingDecision, record *protocol.ErrorRecord, status int) {
	var routeID string
	if decision != nil {
		routeID = decision.ID
	}
	decisionLog := protocol.DecisionLog{
		ID:              routing.NewID("decision_log"),
		SchemaVersion:   protocol.SchemaVersion,
		RequestID:       request.ID,
		Identity:        request.Identity,
		CapabilityID:    request.CapabilityID,
		RoutingStrategy: "none",
		RoutingContext:  map[string]any{"snapshot_version": h.Snapshot.SnapshotVersion},
		Outcome:         "failure",
		UsageEventIDs:   []string{},
		CreatedAt:       time.Now().UTC(),
	}
	if decision != nil {
		decisionLog.RoutingDecisionID = &decision.ID
	}
	_, _ = h.Events.Write(ctx, "decision_log", decisionLog)
	writeJSON(w, status, ExecuteResponse{
		RequestID:         request.ID,
		RoutingDecisionID: routeID,
		Success:           false,
		Error:             record,
	})
}

func validBearer(header, expected string) bool {
	const prefix = "Bearer "
	if !strings.HasPrefix(header, prefix) {
		return false
	}
	return strings.TrimSpace(strings.TrimPrefix(header, prefix)) == expected
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
