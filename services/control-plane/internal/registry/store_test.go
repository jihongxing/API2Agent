package registry

import (
	"context"
	"errors"
	"path/filepath"
	"testing"
)

func TestFileStoreLoadsRegistry(t *testing.T) {
	store := NewFileStore(filepath.Join("..", "..", "testdata", "registry", "network.public_ip.get.json"))

	reg, err := store.Load(context.Background())
	if err != nil {
		t.Fatalf("load registry: %v", err)
	}
	if len(reg.Projects) != 1 || reg.Projects[0].ID != "local" {
		t.Fatalf("unexpected projects: %#v", reg.Projects)
	}
}

func TestFileStoreHonorsCanceledContext(t *testing.T) {
	store := NewFileStore(filepath.Join("..", "..", "testdata", "registry", "network.public_ip.get.json"))
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	_, err := store.Load(ctx)
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", err)
	}
}

func TestFileStoreRequiresPath(t *testing.T) {
	_, err := NewFileStore("").Load(context.Background())
	if err == nil {
		t.Fatalf("expected missing path error")
	}
}
