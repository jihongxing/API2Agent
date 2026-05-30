package events

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

type sequencedTestRecord struct {
	Name            string `json:"name"`
	EventSequenceID int64  `json:"event_sequence_id"`
}

func (r *sequencedTestRecord) SetEventSequenceID(sequenceID int64) {
	r.EventSequenceID = sequenceID
}

func TestJSONLWriterResumesSequenceAfterRestart(t *testing.T) {
	dir := t.TempDir()
	writer, err := NewJSONLWriter(dir)
	if err != nil {
		t.Fatalf("create writer: %v", err)
	}
	first := &sequencedTestRecord{Name: "first"}
	seq, err := writer.Write(context.Background(), "test_event", first)
	if err != nil {
		t.Fatalf("write first: %v", err)
	}
	if seq != 1 || first.EventSequenceID != 1 {
		t.Fatalf("expected first sequence 1, got seq=%d record=%d", seq, first.EventSequenceID)
	}

	restarted, err := NewJSONLWriter(dir)
	if err != nil {
		t.Fatalf("restart writer: %v", err)
	}
	second := &sequencedTestRecord{Name: "second"}
	seq, err = restarted.Write(context.Background(), "test_event", second)
	if err != nil {
		t.Fatalf("write second: %v", err)
	}
	if seq != 2 || second.EventSequenceID != 2 {
		t.Fatalf("expected second sequence 2, got seq=%d record=%d", seq, second.EventSequenceID)
	}

	envelopes := readTestEnvelopes(t, filepath.Join(dir, "events.jsonl"))
	if len(envelopes) != 2 {
		t.Fatalf("expected 2 envelopes, got %d", len(envelopes))
	}
	if envelopes[0].EventSequenceID != 1 || envelopes[1].EventSequenceID != 2 {
		t.Fatalf("unexpected persisted sequences: %#v", envelopes)
	}
}

func TestJSONLWriterRejectsCorruptExistingLog(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "events.jsonl"), []byte("{not-json}\n"), 0o644); err != nil {
		t.Fatalf("write corrupt log: %v", err)
	}
	if _, err := NewJSONLWriter(dir); err == nil {
		t.Fatalf("expected corrupt log to fail writer startup")
	}
}

func readTestEnvelopes(t *testing.T, path string) []Envelope {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read event log: %v", err)
	}
	var envelopes []Envelope
	for _, line := range splitNonEmptyLines(data) {
		var envelope Envelope
		if err := json.Unmarshal(line, &envelope); err != nil {
			t.Fatalf("decode envelope: %v", err)
		}
		envelopes = append(envelopes, envelope)
	}
	return envelopes
}

func splitNonEmptyLines(data []byte) [][]byte {
	var lines [][]byte
	start := 0
	for index, value := range data {
		if value != '\n' {
			continue
		}
		if index > start {
			lines = append(lines, data[start:index])
		}
		start = index + 1
	}
	if start < len(data) {
		lines = append(lines, data[start:])
	}
	return lines
}
