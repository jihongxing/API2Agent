package registry

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
)

type Store interface {
	Load(ctx context.Context) (*Registry, error)
}

type FileStore struct {
	Path string
}

func NewFileStore(path string) FileStore {
	return FileStore{Path: path}
}

func (s FileStore) Load(ctx context.Context) (*Registry, error) {
	if s.Path == "" {
		return nil, fmt.Errorf("registry path is required")
	}
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	default:
	}
	data, err := os.ReadFile(s.Path)
	if err != nil {
		return nil, fmt.Errorf("read registry: %w", err)
	}
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	default:
	}
	var registry Registry
	if err := json.Unmarshal(data, &registry); err != nil {
		return nil, fmt.Errorf("decode registry: %w", err)
	}
	if err := registry.Validate(); err != nil {
		return nil, err
	}
	return &registry, nil
}

func LoadFile(path string) (*Registry, error) {
	return NewFileStore(path).Load(context.Background())
}
