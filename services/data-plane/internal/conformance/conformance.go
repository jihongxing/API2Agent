package conformance

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"

	"api2agent/services/data-plane/internal/protocol"
)

type Schema struct {
	Defs map[string]Definition `json:"$defs"`
}

type Definition struct {
	AdditionalProperties bool                       `json:"additionalProperties"`
	Required             []string                   `json:"required"`
	Properties           map[string]json.RawMessage `json:"properties"`
}

type EventEnvelope struct {
	EventType       string          `json:"event_type"`
	EventSequenceID int64           `json:"event_sequence_id"`
	Record          json.RawMessage `json:"record"`
}

func DefaultSchemaPath() (string, error) {
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		return "", fmt.Errorf("resolve conformance package path")
	}
	return filepath.Clean(filepath.Join(filepath.Dir(file), "..", "..", "..", "..", "schemas", "api2agent", "v0.2", "protocol.schema.json")), nil
}

func LoadDefaultSchema() (*Schema, error) {
	path, err := DefaultSchemaPath()
	if err != nil {
		return nil, err
	}
	return LoadSchemaFile(path)
}

func LoadSchemaFile(path string) (*Schema, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read protocol schema %s: %w", path, err)
	}
	var schema Schema
	if err := json.Unmarshal(data, &schema); err != nil {
		return nil, fmt.Errorf("decode protocol schema: %w", err)
	}
	return &schema, nil
}

func (s *Schema) ValidateRecord(definitionName string, record any) error {
	data, err := json.Marshal(record)
	if err != nil {
		return fmt.Errorf("marshal %s: %w", definitionName, err)
	}
	return s.ValidateJSON(definitionName, data)
}

func (s *Schema) ValidateJSON(definitionName string, data []byte) error {
	definition, ok := s.Defs[definitionName]
	if !ok {
		return fmt.Errorf("schema definition %q not found", definitionName)
	}
	var payload map[string]any
	if err := json.Unmarshal(data, &payload); err != nil {
		return fmt.Errorf("decode %s JSON: %w", definitionName, err)
	}
	for _, required := range definition.Required {
		if _, ok := payload[required]; !ok {
			return fmt.Errorf("%s missing required schema field %q", definitionName, required)
		}
	}
	if definition.AdditionalProperties == false {
		for key := range payload {
			if _, ok := definition.Properties[key]; !ok {
				return fmt.Errorf("%s emitted field %q not present in schema snapshot", definitionName, key)
			}
		}
	}
	if got, ok := payload["schema_version"].(string); ok && got != protocol.SchemaVersion {
		return fmt.Errorf("%s schema_version = %q, want %q", definitionName, got, protocol.SchemaVersion)
	}
	return nil
}

func (s *Schema) ValidateEventEnvelopeJSON(data []byte) (string, error) {
	var envelope EventEnvelope
	if err := json.Unmarshal(data, &envelope); err != nil {
		return "", fmt.Errorf("decode event envelope: %w", err)
	}
	if envelope.EventSequenceID <= 0 {
		return envelope.EventType, fmt.Errorf("event %q missing positive event_sequence_id", envelope.EventType)
	}
	definitionName, ok := DefinitionForEventType(envelope.EventType)
	if !ok {
		return envelope.EventType, fmt.Errorf("unsupported event_type %q", envelope.EventType)
	}
	if len(envelope.Record) == 0 {
		return envelope.EventType, fmt.Errorf("event %q missing record", envelope.EventType)
	}
	if err := s.ValidateJSON(definitionName, envelope.Record); err != nil {
		return envelope.EventType, err
	}
	return envelope.EventType, nil
}

func DefinitionForEventType(eventType string) (string, bool) {
	switch eventType {
	case "request_context":
		return "RequestContext", true
	case "routing_decision":
		return "RoutingDecision", true
	case "usage_event":
		return "UsageEvent", true
	case "decision_log":
		return "DecisionLog", true
	default:
		return "", false
	}
}
