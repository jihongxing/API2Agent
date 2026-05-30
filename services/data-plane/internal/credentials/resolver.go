package credentials

import (
	"fmt"
	"os"
	"strings"
	"time"
)

type LocalResolver struct{}

func NewLocalResolver() LocalResolver {
	return LocalResolver{}
}

func (r LocalResolver) Resolve(request CredentialResolutionRequest) ResolvedCredential {
	if request.Credential == nil {
		return ResolvedCredential{
			Resolved:            true,
			CredentialReference: "none",
			RedactedMetadata: map[string]any{
				"source":      "none",
				"provider_id": request.ProviderID,
			},
		}
	}

	credential := *request.Credential
	if credential.ProviderID != "" && credential.ProviderID != request.ProviderID {
		return r.denied(credential, request, "credential_provider_mismatch", "Credential provider does not match request provider")
	}
	if strings.EqualFold(credential.Status, "disabled") {
		return r.denied(credential, request, "credential_disabled", "Credential is disabled")
	}
	if credential.ExpiresAt != nil && !credential.ExpiresAt.After(time.Now().UTC()) {
		return r.denied(credential, request, "credential_expired", "Credential is expired")
	}

	secret, credentialReference, ok := r.secretFor(credential)
	if !ok {
		return r.denied(credential, request, "missing_credential_secret", "Credential secret is unavailable")
	}
	patch := r.injectionPatch(credential, secret)
	return ResolvedCredential{
		Resolved:            true,
		CredentialReference: credentialReference,
		InjectionPatch:      patch,
		RedactedMetadata:    r.redactedMetadata(credential),
	}
}

func (r LocalResolver) secretFor(credential CredentialDefinition) (string, string, bool) {
	switch strings.ToLower(credential.Source) {
	case "", "none":
		return "", "none", true
	case "env":
		if credential.SecretRef == "" {
			return "", "", false
		}
		value := os.Getenv(credential.SecretRef)
		if value == "" {
			return "", "", false
		}
		return value, fmt.Sprintf("env:%s", credential.SecretRef), true
	default:
		return "", "", false
	}
}

func (r LocalResolver) injectionPatch(credential CredentialDefinition, secret string) CredentialPatch {
	name := credential.InjectionName
	if name == "" {
		name = defaultInjectionName(credential.AuthType)
	}
	value := formattedSecret(credential.AuthType, secret)
	switch strings.ToLower(credential.InjectionMode) {
	case "query":
		return CredentialPatch{Query: map[string]string{name: value}}
	case "body":
		return CredentialPatch{Body: map[string]string{name: value}}
	default:
		return CredentialPatch{Headers: map[string]string{name: value}}
	}
}

func (r LocalResolver) redactedMetadata(credential CredentialDefinition) map[string]any {
	return map[string]any{
		"credential_id":  credential.CredentialID,
		"owner_type":     credential.OwnerType,
		"owner_id":       credential.OwnerID,
		"provider_id":    credential.ProviderID,
		"auth_type":      credential.AuthType,
		"injection_mode": credential.InjectionMode,
		"injection_name": credential.InjectionName,
		"source":         credential.Source,
		"secret_ref":     credential.SecretRef,
		"scope":          credential.Scope,
		"status":         credential.Status,
		"expires_at":     credentialExpiresAt(credential.ExpiresAt),
		"rotation_hint":  credential.RotationHint,
	}
}

func (r LocalResolver) denied(credential CredentialDefinition, request CredentialResolutionRequest, errorType, message string) ResolvedCredential {
	reference := "missing"
	if credential.CredentialID != "" {
		reference = credentialReference(credential)
	}
	return ResolvedCredential{
		Resolved:            false,
		CredentialReference: reference,
		RedactedMetadata:    r.redactedMetadata(credential),
		ErrorType:           errorType,
		ErrorMessage:        message,
	}
}

func credentialReference(credential CredentialDefinition) string {
	switch strings.ToLower(credential.Source) {
	case "env":
		if credential.SecretRef != "" {
			return fmt.Sprintf("env:%s", credential.SecretRef)
		}
	case "config":
		return fmt.Sprintf("config:%s", credential.CredentialID)
	case "inline":
		return fmt.Sprintf("inline:%s", credential.CredentialID)
	}
	if credential.CredentialID != "" {
		return fmt.Sprintf("credential:%s", credential.CredentialID)
	}
	return "missing"
}

func credentialExpiresAt(value *time.Time) string {
	if value == nil {
		return ""
	}
	return value.UTC().Format(time.RFC3339)
}

func defaultInjectionName(authType string) string {
	switch strings.ToLower(authType) {
	case "bearer", "basic":
		return "Authorization"
	default:
		return "X-API-Key"
	}
}

func formattedSecret(authType, secret string) string {
	switch strings.ToLower(authType) {
	case "bearer":
		if strings.HasPrefix(strings.ToLower(secret), "bearer ") {
			return secret
		}
		return "Bearer " + secret
	case "basic":
		if strings.HasPrefix(strings.ToLower(secret), "basic ") {
			return secret
		}
		return "Basic " + secret
	default:
		return secret
	}
}
