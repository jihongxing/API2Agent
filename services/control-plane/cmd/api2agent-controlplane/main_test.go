package main

import (
	"context"
	"strings"
	"testing"
)

func TestOpenRegistryRuntimeDefaultsToFile(t *testing.T) {
	runtime, err := openRegistryRuntime(context.Background(), "", "registry.json", "")
	if err != nil {
		t.Fatalf("open registry runtime: %v", err)
	}
	if runtime.StoreName != "file" || runtime.Source != "registry.json" {
		t.Fatalf("unexpected runtime: %#v", runtime)
	}
	if runtime.Close() != nil {
		t.Fatalf("file runtime close should be nil")
	}
}

func TestOpenRegistryRuntimeRequiresRegistryForFileStore(t *testing.T) {
	_, err := openRegistryRuntime(context.Background(), "file", "", "")
	if err == nil {
		t.Fatalf("expected missing registry error")
	}
	if !strings.Contains(err.Error(), "--registry is required") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestOpenRegistryRuntimeRequiresPostgresDSN(t *testing.T) {
	_, err := openRegistryRuntime(context.Background(), "postgres", "", "")
	if err == nil {
		t.Fatalf("expected missing postgres dsn error")
	}
	if !strings.Contains(err.Error(), "--postgres-dsn is required") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestOpenRegistryRuntimeRejectsUnknownStore(t *testing.T) {
	_, err := openRegistryRuntime(context.Background(), "sqlite", "", "")
	if err == nil {
		t.Fatalf("expected invalid registry store error")
	}
	if !strings.Contains(err.Error(), "--registry-store must be file or postgres") {
		t.Fatalf("unexpected error: %v", err)
	}
}
