package credentials

import "time"

type CredentialDefinition struct {
	CredentialID      string     `json:"credential_id"`
	CredentialVersion string     `json:"credential_version,omitempty"`
	OwnerType         string     `json:"owner_type,omitempty"`
	OwnerID           string     `json:"owner_id,omitempty"`
	ProviderID        string     `json:"provider_id"`
	AuthType          string     `json:"auth_type,omitempty"`
	InjectionMode     string     `json:"injection_mode,omitempty"`
	InjectionName     string     `json:"injection_name,omitempty"`
	Source            string     `json:"source,omitempty"`
	SecretRef         string     `json:"secret_ref,omitempty"`
	Scope             []string   `json:"scope,omitempty"`
	Status            string     `json:"status,omitempty"`
	ExpiresAt         *time.Time `json:"expires_at,omitempty"`
	RotationHint      string     `json:"rotation_hint,omitempty"`
}

type CredentialResolutionRequest struct {
	ProjectID    string
	AgentID      *string
	CapabilityID string
	ProviderID   string
	ToolID       string
	Credential   *CredentialDefinition
}

type CredentialPatch struct {
	Headers map[string]string `json:"headers,omitempty"`
	Query   map[string]string `json:"query,omitempty"`
	Body    map[string]string `json:"body,omitempty"`
}

type ResolvedCredential struct {
	Resolved            bool
	CredentialReference string
	InjectionPatch      CredentialPatch
	RedactedMetadata    map[string]any
	ResolvedAt          time.Time
	ErrorType           string
	ErrorMessage        string
}
