package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sort"

	"api2agent/services/data-plane/internal/conformance"
)

type Report struct {
	EventsPath          string         `json:"events_path"`
	EventCount          int            `json:"event_count"`
	ValidatedEventTypes map[string]int `json:"validated_event_types"`
	Passed              bool           `json:"passed"`
	Error               string         `json:"error,omitempty"`
}

func main() {
	eventsPath := flag.String("events", "", "path to JSONL event log")
	schemaPath := flag.String("schema", "", "optional protocol schema path")
	flag.Parse()

	report, err := run(*eventsPath, *schemaPath)
	if err != nil {
		report.Passed = false
		report.Error = err.Error()
		_ = json.NewEncoder(os.Stdout).Encode(report)
		os.Exit(1)
	}
	report.Passed = true
	_ = json.NewEncoder(os.Stdout).Encode(report)
}

func run(eventsPath string, schemaPath string) (Report, error) {
	report := Report{EventsPath: eventsPath, ValidatedEventTypes: map[string]int{}}
	if eventsPath == "" {
		return report, fmt.Errorf("--events is required")
	}
	var schema *conformance.Schema
	var err error
	if schemaPath == "" {
		schema, err = conformance.LoadDefaultSchema()
	} else {
		schema, err = conformance.LoadSchemaFile(schemaPath)
	}
	if err != nil {
		return report, err
	}

	file, err := os.Open(eventsPath)
	if err != nil {
		return report, fmt.Errorf("open events: %w", err)
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	lineNumber := 0
	for scanner.Scan() {
		lineNumber++
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}
		eventType, err := schema.ValidateEventEnvelopeJSON(line)
		if err != nil {
			return report, fmt.Errorf("line %d: %w", lineNumber, err)
		}
		report.EventCount++
		report.ValidatedEventTypes[eventType]++
	}
	if err := scanner.Err(); err != nil {
		return report, fmt.Errorf("scan events: %w", err)
	}
	if report.EventCount == 0 {
		return report, fmt.Errorf("no events to validate")
	}
	normalizeEventTypeOrder(report.ValidatedEventTypes)
	return report, nil
}

func normalizeEventTypeOrder(values map[string]int) {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
}
