package events

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type Envelope struct {
	EventType       string    `json:"event_type"`
	EventSequenceID int64     `json:"event_sequence_id"`
	RecordedAt      time.Time `json:"recorded_at"`
	Record          any       `json:"record"`
}

type Writer interface {
	Write(ctx context.Context, eventType string, record any) (int64, error)
}

type sequencedRecord interface {
	SetEventSequenceID(int64)
}

type JSONLWriter struct {
	mu       sync.Mutex
	nextSeq  int64
	filePath string
}

func NewJSONLWriter(dir string) (*JSONLWriter, error) {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return nil, err
	}
	filePath := filepath.Join(dir, "events.jsonl")
	nextSeq, err := nextSequence(filePath)
	if err != nil {
		return nil, err
	}
	return &JSONLWriter{nextSeq: nextSeq, filePath: filePath}, nil
}

func (w *JSONLWriter) Write(ctx context.Context, eventType string, record any) (int64, error) {
	w.mu.Lock()
	defer w.mu.Unlock()

	seq := w.nextSeq
	w.nextSeq++
	if sequenced, ok := record.(sequencedRecord); ok {
		sequenced.SetEventSequenceID(seq)
	}
	envelope := Envelope{
		EventType:       eventType,
		EventSequenceID: seq,
		RecordedAt:      time.Now().UTC(),
		Record:          record,
	}
	data, err := json.Marshal(envelope)
	if err != nil {
		return 0, err
	}
	select {
	case <-ctx.Done():
		return 0, ctx.Err()
	default:
	}
	file, err := os.OpenFile(w.filePath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return 0, err
	}
	defer file.Close()
	if _, err := file.Write(append(data, '\n')); err != nil {
		return 0, err
	}
	if err := file.Sync(); err != nil {
		return 0, err
	}
	return seq, nil
}

func nextSequence(filePath string) (int64, error) {
	file, err := os.Open(filePath)
	if err != nil {
		if os.IsNotExist(err) {
			return 1, nil
		}
		return 0, err
	}
	defer file.Close()

	var maxSeq int64
	scanner := bufio.NewScanner(file)
	lineNumber := 0
	for scanner.Scan() {
		lineNumber++
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}
		var envelope Envelope
		if err := json.Unmarshal(line, &envelope); err != nil {
			return 0, fmt.Errorf("decode event log line %d: %w", lineNumber, err)
		}
		if envelope.EventSequenceID > maxSeq {
			maxSeq = envelope.EventSequenceID
		}
	}
	if err := scanner.Err(); err != nil {
		return 0, err
	}
	return maxSeq + 1, nil
}

type MemoryWriter struct {
	mu      sync.Mutex
	nextSeq int64
	Events  []Envelope
}

func NewMemoryWriter() *MemoryWriter {
	return &MemoryWriter{nextSeq: 1}
}

func (w *MemoryWriter) Write(ctx context.Context, eventType string, record any) (int64, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	seq := w.nextSeq
	w.nextSeq++
	if sequenced, ok := record.(sequencedRecord); ok {
		sequenced.SetEventSequenceID(seq)
	}
	envelope := Envelope{
		EventType:       eventType,
		EventSequenceID: seq,
		RecordedAt:      time.Now().UTC(),
		Record:          record,
	}
	w.Events = append(w.Events, envelope)
	return seq, nil
}
