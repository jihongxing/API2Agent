package conformance

import (
	"encoding/json"
	"testing"
	"time"

	"api2agent/services/data-plane/internal/protocol"
)

func TestValidateRecordAcceptsProtocolObject(t *testing.T) {
	schema, err := LoadDefaultSchema()
	if err != nil {
		t.Fatalf("load schema: %v", err)
	}
	record := protocol.RequestContext{
		ID:                "req_test",
		SchemaVersion:     protocol.SchemaVersion,
		Identity:          protocol.IdentityRef{ProjectID: "local"},
		CapabilityID:      "network.public_ip.get",
		CapabilityVersion: "0.1-migrated",
		ExecutionMode:     "proxy",
		CreatedAt:         time.Now().UTC(),
	}
	if err := schema.ValidateRecord("RequestContext", record); err != nil {
		t.Fatalf("validate request context: %v", err)
	}
}

func TestValidateJSONRejectsUnknownFields(t *testing.T) {
	schema, err := LoadDefaultSchema()
	if err != nil {
		t.Fatalf("load schema: %v", err)
	}
	payload := map[string]any{
		"id":                 "req_test",
		"schema_version":     protocol.SchemaVersion,
		"identity":           map[string]any{"project_id": "local"},
		"capability_id":      "network.public_ip.get",
		"capability_version": "0.1-migrated",
		"execution_mode":     "proxy",
		"created_at":         time.Now().UTC().Format(time.RFC3339),
		"unexpected":         true,
	}
	data, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("marshal payload: %v", err)
	}
	if err := schema.ValidateJSON("RequestContext", data); err == nil {
		t.Fatalf("expected unknown field to fail validation")
	}
}

func TestValidateEventEnvelopeJSON(t *testing.T) {
	schema, err := LoadDefaultSchema()
	if err != nil {
		t.Fatalf("load schema: %v", err)
	}
	record := protocol.DecisionLog{
		ID:              "decision_log_test",
		SchemaVersion:   protocol.SchemaVersion,
		RequestID:       "req_test",
		Identity:        protocol.IdentityRef{ProjectID: "local"},
		CapabilityID:    "network.public_ip.get",
		RoutingStrategy: "first",
		Outcome:         "success",
		UsageEventIDs:   []string{"usage_test"},
		EventSequenceID: 1,
		CreatedAt:       time.Now().UTC(),
	}
	envelope := map[string]any{
		"event_type":        "decision_log",
		"event_sequence_id": 1,
		"recorded_at":       time.Now().UTC(),
		"record":            record,
	}
	data, err := json.Marshal(envelope)
	if err != nil {
		t.Fatalf("marshal envelope: %v", err)
	}
	if _, err := schema.ValidateEventEnvelopeJSON(data); err != nil {
		t.Fatalf("validate envelope: %v", err)
	}
}
