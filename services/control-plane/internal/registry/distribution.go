package registry

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

func ReadManifestFile(path string) (ExportArtifactManifest, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return ExportArtifactManifest{}, fmt.Errorf("read manifest: %w", err)
	}
	var manifest ExportArtifactManifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return ExportArtifactManifest{}, fmt.Errorf("decode manifest: %w", err)
	}
	if manifest.SnapshotFile == "" {
		return ExportArtifactManifest{}, fmt.Errorf("manifest snapshot_file is required")
	}
	if manifest.SnapshotVersion == "" {
		return ExportArtifactManifest{}, fmt.Errorf("manifest snapshot_version is required")
	}
	return manifest, nil
}

func WriteDistributionPointer(path string, pointer SnapshotDistributionPointer) error {
	data, err := json.MarshalIndent(pointer, "", "  ")
	if err != nil {
		return fmt.Errorf("encode distribution pointer: %w", err)
	}
	data = append(data, '\n')
	if err := os.WriteFile(path, data, 0o644); err != nil {
		return fmt.Errorf("write distribution pointer: %w", err)
	}
	return nil
}

func PublishArtifactDir(sourceArtifactDir string, distributionDir string, publishedAt time.Time) (SnapshotDistributionPointer, error) {
	if sourceArtifactDir == "" {
		return SnapshotDistributionPointer{}, fmt.Errorf("artifact dir is required")
	}
	if distributionDir == "" {
		return SnapshotDistributionPointer{}, fmt.Errorf("distribution dir is required")
	}
	manifest, err := ReadManifestFile(filepath.Join(sourceArtifactDir, "manifest.json"))
	if err != nil {
		return SnapshotDistributionPointer{}, err
	}
	if err := validateSnapshotVersionForPath(manifest.SnapshotVersion); err != nil {
		return SnapshotDistributionPointer{}, err
	}
	sourceSnapshot := filepath.Join(sourceArtifactDir, manifest.SnapshotFile)
	if _, err := os.Stat(sourceSnapshot); err != nil {
		return SnapshotDistributionPointer{}, fmt.Errorf("stat snapshot artifact: %w", err)
	}

	relativeArtifactDir := filepath.ToSlash(filepath.Join("artifacts", manifest.SnapshotVersion))
	targetArtifactDir := filepath.Join(distributionDir, "artifacts", manifest.SnapshotVersion)
	if err := os.MkdirAll(targetArtifactDir, 0o755); err != nil {
		return SnapshotDistributionPointer{}, fmt.Errorf("create distribution artifact dir: %w", err)
	}
	if err := copyFile(sourceSnapshot, filepath.Join(targetArtifactDir, "snapshot.json")); err != nil {
		return SnapshotDistributionPointer{}, err
	}
	if err := copyFile(filepath.Join(sourceArtifactDir, "manifest.json"), filepath.Join(targetArtifactDir, "manifest.json")); err != nil {
		return SnapshotDistributionPointer{}, err
	}

	pointer := SnapshotDistributionPointer{
		DistributionVersion:   "api2agent.snapshot_distribution.v0",
		PublishedAt:           publishedAt.UTC(),
		SnapshotVersion:       manifest.SnapshotVersion,
		ArtifactDir:           relativeArtifactDir,
		SnapshotFile:          filepath.ToSlash(filepath.Join(relativeArtifactDir, "snapshot.json")),
		ManifestFile:          filepath.ToSlash(filepath.Join(relativeArtifactDir, "manifest.json")),
		RegistryFingerprint:   manifest.RegistryFingerprint,
		SnapshotVersionPolicy: manifest.SnapshotVersionPolicy,
		SourceArtifactDir:     sourceArtifactDir,
	}
	if err := os.MkdirAll(distributionDir, 0o755); err != nil {
		return SnapshotDistributionPointer{}, fmt.Errorf("create distribution dir: %w", err)
	}
	if err := WriteDistributionPointer(filepath.Join(distributionDir, "current.json"), pointer); err != nil {
		return SnapshotDistributionPointer{}, err
	}
	return pointer, nil
}

func copyFile(src string, dst string) error {
	data, err := os.ReadFile(src)
	if err != nil {
		return fmt.Errorf("read artifact file: %w", err)
	}
	if err := os.WriteFile(dst, data, 0o644); err != nil {
		return fmt.Errorf("write distribution artifact file: %w", err)
	}
	return nil
}

func validateSnapshotVersionForPath(version string) error {
	if version == "" {
		return fmt.Errorf("snapshot version is required")
	}
	if version == "." || version == ".." || strings.Contains(version, "/") || strings.Contains(version, "\\") {
		return fmt.Errorf("snapshot version %q is not safe for distribution path", version)
	}
	return nil
}
