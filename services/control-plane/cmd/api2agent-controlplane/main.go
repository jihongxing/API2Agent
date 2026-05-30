package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"time"

	"api2agent/services/control-plane/internal/registry"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	switch os.Args[1] {
	case "export-snapshot":
		if err := exportSnapshot(os.Args[2:]); err != nil {
			log.Fatalf("export snapshot: %v", err)
		}
	case "export-artifact":
		if err := exportArtifact(os.Args[2:]); err != nil {
			log.Fatalf("export artifact: %v", err)
		}
	case "publish-artifact":
		if err := publishArtifact(os.Args[2:]); err != nil {
			log.Fatalf("publish artifact: %v", err)
		}
	default:
		usage()
		os.Exit(2)
	}
}

func exportSnapshot(args []string) error {
	flags := flag.NewFlagSet("export-snapshot", flag.ExitOnError)
	registryPath := flags.String("registry", "", "path to control plane registry json")
	outputPath := flags.String("output", "", "path to write routing snapshot json")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if *registryPath == "" {
		return fmt.Errorf("--registry is required")
	}
	if *outputPath == "" {
		return fmt.Errorf("--output is required")
	}
	store := registry.NewFileStore(*registryPath)
	reg, err := store.Load(context.Background())
	if err != nil {
		return err
	}
	snapshot, err := reg.ExportSnapshot()
	if err != nil {
		return err
	}
	return registry.WriteSnapshotFile(*outputPath, snapshot)
}

func exportArtifact(args []string) error {
	flags := flag.NewFlagSet("export-artifact", flag.ExitOnError)
	registryPath := flags.String("registry", "", "path to control plane registry json")
	outputDir := flags.String("output-dir", "", "directory to write snapshot artifact")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if *registryPath == "" {
		return fmt.Errorf("--registry is required")
	}
	if *outputDir == "" {
		return fmt.Errorf("--output-dir is required")
	}
	store := registry.NewFileStore(*registryPath)
	reg, err := store.Load(context.Background())
	if err != nil {
		return err
	}
	snapshot, manifest, err := reg.ExportArtifact(time.Now().UTC(), "file", *registryPath)
	if err != nil {
		return err
	}
	return registry.WriteArtifactDir(*outputDir, snapshot, manifest)
}

func publishArtifact(args []string) error {
	flags := flag.NewFlagSet("publish-artifact", flag.ExitOnError)
	artifactDir := flags.String("artifact-dir", "", "directory containing snapshot.json and manifest.json")
	distributionDir := flags.String("distribution-dir", "", "directory to publish current snapshot distribution")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if *artifactDir == "" {
		return fmt.Errorf("--artifact-dir is required")
	}
	if *distributionDir == "" {
		return fmt.Errorf("--distribution-dir is required")
	}
	_, err := registry.PublishArtifactDir(*artifactDir, *distributionDir, time.Now().UTC())
	return err
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage:")
	fmt.Fprintln(os.Stderr, "  api2agent-controlplane export-snapshot --registry <registry.json> --output <snapshot.json>")
	fmt.Fprintln(os.Stderr, "  api2agent-controlplane export-artifact --registry <registry.json> --output-dir <artifact-dir>")
	fmt.Fprintln(os.Stderr, "  api2agent-controlplane publish-artifact --artifact-dir <artifact-dir> --distribution-dir <distribution-dir>")
}
