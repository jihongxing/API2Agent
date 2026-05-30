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
	if manifest.RegistryFingerprint == "" {
		return ExportArtifactManifest{}, fmt.Errorf("manifest registry_fingerprint is required")
	}
	if manifest.SnapshotVersionPolicy == "" {
		return ExportArtifactManifest{}, fmt.Errorf("manifest snapshot_version_policy is required")
	}
	if manifest.SnapshotDigest == "" {
		return ExportArtifactManifest{}, fmt.Errorf("manifest snapshot_digest is required")
	}
	return manifest, nil
}

func ReadArtifactDir(dir string) (RoutingSnapshot, ExportArtifactManifest, error) {
	manifest, err := ReadManifestFile(filepath.Join(dir, "manifest.json"))
	if err != nil {
		return RoutingSnapshot{}, ExportArtifactManifest{}, err
	}
	snapshotPath, err := safeJoinRelative(dir, manifest.SnapshotFile, "manifest snapshot_file", "artifact")
	if err != nil {
		return RoutingSnapshot{}, ExportArtifactManifest{}, err
	}
	snapshot, err := ReadSnapshotFile(snapshotPath)
	if err != nil {
		return RoutingSnapshot{}, ExportArtifactManifest{}, err
	}
	if err := ValidateArtifactConsistency(snapshot, manifest); err != nil {
		return RoutingSnapshot{}, ExportArtifactManifest{}, err
	}
	fileDigest, err := FileDigest(snapshotPath)
	if err != nil {
		return RoutingSnapshot{}, ExportArtifactManifest{}, err
	}
	if manifest.SnapshotDigest != fileDigest {
		return RoutingSnapshot{}, ExportArtifactManifest{}, fmt.Errorf("manifest snapshot_digest %q does not match snapshot file digest %q", manifest.SnapshotDigest, fileDigest)
	}
	return snapshot, manifest, nil
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
	_, manifest, err := ReadArtifactDir(sourceArtifactDir)
	if err != nil {
		return SnapshotDistributionPointer{}, err
	}
	if err := validateSnapshotVersionForPath(manifest.SnapshotVersion); err != nil {
		return SnapshotDistributionPointer{}, err
	}
	sourceSnapshot, err := safeJoinRelative(sourceArtifactDir, manifest.SnapshotFile, "manifest snapshot_file", "artifact")
	if err != nil {
		return SnapshotDistributionPointer{}, err
	}
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
		SnapshotDigest:        manifest.SnapshotDigest,
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

func safeJoinRelative(baseDir string, reference string, field string, scope string) (string, error) {
	if reference == "" {
		return "", fmt.Errorf("%s is required", field)
	}
	relativePath := filepath.FromSlash(reference)
	if filepath.IsAbs(relativePath) {
		return "", fmt.Errorf("%s %q is not safe for %s path", field, reference, scope)
	}
	cleanPath := filepath.Clean(relativePath)
	if cleanPath == "." || cleanPath == ".." || strings.HasPrefix(cleanPath, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("%s %q is not safe for %s path", field, reference, scope)
	}
	return filepath.Join(baseDir, cleanPath), nil
}
