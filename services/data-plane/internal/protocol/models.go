package protocol

import "time"

const SchemaVersion = "api2agent.protocol.v0.2"

type IdentityRef struct {
	ProjectID string  `json:"project_id"`
	UserID    *string `json:"user_id,omitempty"`
	APIKeyID  *string `json:"api_key_id,omitempty"`
	AgentID   *string `json:"agent_id,omitempty"`
}

type RequestContext struct {
	ID                string      `json:"id"`
	SchemaVersion     string      `json:"schema_version"`
	Identity          IdentityRef `json:"identity"`
	CapabilityID      string      `json:"capability_id"`
	CapabilityVersion string      `json:"capability_version"`
	InputFingerprint  *string     `json:"input_fingerprint,omitempty"`
	ExecutionMode     string      `json:"execution_mode"`
	ClientRegion      *string     `json:"client_region,omitempty"`
	CreatedAt         time.Time   `json:"created_at"`
}

type NetworkTopology struct {
	ClientRegion           *string  `json:"client_region,omitempty"`
	EdgeRegion             *string  `json:"edge_region,omitempty"`
	API2AgentRegion        *string  `json:"api2agent_region,omitempty"`
	ProviderRegion         *string  `json:"provider_region,omitempty"`
	SelectedProviderRegion *string  `json:"selected_provider_region,omitempty"`
	RoutePath              []string `json:"route_path,omitempty"`
}

type LatencyProfile struct {
	LatencyMS         *float64       `json:"latency_ms,omitempty"`
	LatencyNetworkMS  *float64       `json:"latency_network_ms,omitempty"`
	LatencyProviderMS *float64       `json:"latency_provider_ms,omitempty"`
	LatencyOverheadMS *float64       `json:"latency_overhead_ms,omitempty"`
	LatencyRegion     *string        `json:"latency_region,omitempty"`
	MetricsWindow     *MetricsWindow `json:"metrics_window,omitempty"`
}

type MetricsWindow struct {
	Type       *string    `json:"type,omitempty"`
	Size       *string    `json:"size,omitempty"`
	SampleSize *int       `json:"sample_size,omitempty"`
	ObservedAt *time.Time `json:"observed_at,omitempty"`
}

type CostProfile struct {
	EstimatedCost *float64       `json:"estimated_cost,omitempty"`
	ObservedCost  *float64       `json:"observed_cost,omitempty"`
	Currency      *string        `json:"currency,omitempty"`
	Unit          *string        `json:"unit,omitempty"`
	CostSource    *string        `json:"cost_source,omitempty"`
	MetricsWindow *MetricsWindow `json:"metrics_window,omitempty"`
}

type ErrorRecord struct {
	ErrorType  *string `json:"error_type,omitempty"`
	ErrorScope *string `json:"error_scope,omitempty"`
	Message    *string `json:"message,omitempty"`
	Retryable  *bool   `json:"retryable,omitempty"`
}

type FailoverPolicy struct {
	Enabled              bool     `json:"enabled"`
	MaxAttempts          int      `json:"max_attempts"`
	RetryOnErrorTypes    []string `json:"retry_on_error_types,omitempty"`
	RetryOnStatusCodes   []int    `json:"retry_on_status_codes,omitempty"`
	AttemptTimeoutPolicy string   `json:"attempt_timeout_policy,omitempty"`
}

type RoutingDecision struct {
	ID                     string          `json:"id"`
	SchemaVersion          string          `json:"schema_version"`
	RequestID              string          `json:"request_id"`
	Identity               IdentityRef     `json:"identity"`
	CapabilityID           string          `json:"capability_id"`
	Strategy               string          `json:"strategy"`
	Preset                 *string         `json:"preset,omitempty"`
	Topology               NetworkTopology `json:"topology"`
	CandidateProviderIDs   []string        `json:"candidate_provider_ids"`
	RankedProviderIDs      []string        `json:"ranked_provider_ids"`
	SelectedProviderID     *string         `json:"selected_provider_id,omitempty"`
	SelectedProviderRegion *string         `json:"selected_provider_region,omitempty"`
	SnapshotVersion        string          `json:"snapshot_version"`
	RoutingMode            string          `json:"routing_mode"`
	RoutingSeed            *string         `json:"routing_seed,omitempty"`
	FailoverPolicy         *FailoverPolicy `json:"failover_policy,omitempty"`
	CreatedAt              time.Time       `json:"created_at"`
}

type CredentialReference struct {
	CredentialReference *string `json:"credential_reference,omitempty"`
	CredentialID        *string `json:"credential_id,omitempty"`
	OwnerType           *string `json:"owner_type,omitempty"`
	OwnerID             *string `json:"owner_id,omitempty"`
	ProviderID          *string `json:"provider_id,omitempty"`
	AuthType            *string `json:"auth_type,omitempty"`
	InjectionMode       *string `json:"injection_mode,omitempty"`
	Source              *string `json:"source,omitempty"`
	ResolutionStrategy  *string `json:"resolution_strategy,omitempty"`
	Status              *string `json:"status,omitempty"`
}

type UsageEvent struct {
	ID                       string               `json:"id"`
	SchemaVersion            string               `json:"schema_version"`
	RequestID                string               `json:"request_id"`
	RoutingDecisionID        *string              `json:"routing_decision_id,omitempty"`
	ExecutionMode            string               `json:"execution_mode"`
	Identity                 IdentityRef          `json:"identity"`
	CapabilityID             string               `json:"capability_id"`
	CapabilityVersion        string               `json:"capability_version"`
	ProviderID               string               `json:"provider_id"`
	ProviderVersion          string               `json:"provider_version"`
	MappingVersion           string               `json:"mapping_version"`
	ToolID                   string               `json:"tool_id"`
	Method                   *string              `json:"method,omitempty"`
	Path                     *string              `json:"path,omitempty"`
	StatusCode               *int                 `json:"status_code,omitempty"`
	Success                  bool                 `json:"success"`
	Latency                  LatencyProfile       `json:"latency"`
	Topology                 NetworkTopology      `json:"topology"`
	Cost                     CostProfile          `json:"cost"`
	Error                    *ErrorRecord         `json:"error,omitempty"`
	RequestMetadata          map[string]any       `json:"request_metadata,omitempty"`
	CredentialReference      *CredentialReference `json:"credential_reference,omitempty"`
	ProviderRuntimeReference *string              `json:"provider_runtime_reference,omitempty"`
	IsGolden                 bool                 `json:"is_golden"`
	EventSequenceID          int64                `json:"event_sequence_id"`
	ParentAttemptID          *string              `json:"parent_attempt_id,omitempty"`
	CreatedAt                time.Time            `json:"created_at"`
}

func (e *UsageEvent) SetEventSequenceID(sequenceID int64) {
	e.EventSequenceID = sequenceID
}

type DecisionLog struct {
	ID                     string         `json:"id"`
	SchemaVersion          string         `json:"schema_version"`
	RequestID              string         `json:"request_id"`
	RoutingDecisionID      *string        `json:"routing_decision_id"`
	Identity               IdentityRef    `json:"identity"`
	CapabilityID           string         `json:"capability_id"`
	InputFingerprint       *string        `json:"input_fingerprint,omitempty"`
	RoutingStrategy        string         `json:"routing_strategy"`
	RoutingContext         map[string]any `json:"routing_context,omitempty"`
	SelectedProviderID     *string        `json:"selected_provider_id,omitempty"`
	SelectedProviderRegion *string        `json:"selected_provider_region,omitempty"`
	Outcome                string         `json:"outcome"`
	UsageEventIDs          []string       `json:"usage_event_ids"`
	EventSequenceID        int64          `json:"event_sequence_id"`
	CreatedAt              time.Time      `json:"created_at"`
}

func (d *DecisionLog) SetEventSequenceID(sequenceID int64) {
	d.EventSequenceID = sequenceID
}
