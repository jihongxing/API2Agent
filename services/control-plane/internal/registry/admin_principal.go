package registry

const (
	PermissionRegistryValidate                    = "control_plane.registry.validate"
	PermissionRegistryImportReplace               = "control_plane.registry.import_replace"
	PermissionRegistryProjectPartitionReplace     = "control_plane.registry.project_partition_replace"
	PermissionHostedPermissionPolicyDraftWrite    = "control_plane.permission_policy.draft_write"
	PermissionHostedPermissionPolicyRequestReview = "control_plane.permission_policy.request_review"
	PermissionHostedPermissionPolicyPromote       = "control_plane.permission_policy.promote"
	PermissionHostedPermissionPolicyRollback      = "control_plane.permission_policy.rollback"
	PermissionSnapshotExportArtifact              = "control_plane.snapshot.export_artifact"
	PermissionDistributionPublish                 = "control_plane.distribution.publish"
	PermissionDistributionReadCurrent             = "control_plane.distribution.read_current"
	DefaultAdminPrincipalProjectID                = "control_plane"
	AdminAuthMethodLocalAdminToken                = "local_admin_token"
	AdminAuthMethodHostedAdminToken               = "hosted_admin_token"
	AdminAuthMethodTrustedGateway                 = "trusted_gateway"
)

type AdminPrincipal struct {
	SubjectID      string
	ActorID        string
	ProjectID      string
	OrganizationID string
	AuthMethod     string
	TokenID        string
	GatewayKeyID   string
	Roles          []string
	Permissions    []string
	LocalPrivate   bool
}

func (p AdminPrincipal) HasPermission(required string) bool {
	if required == "" {
		return true
	}
	for _, permission := range p.Permissions {
		if permission == required {
			return true
		}
	}
	return false
}

func LocalPrivateAdminPermissions() []string {
	return []string{
		PermissionRegistryValidate,
		PermissionRegistryImportReplace,
		PermissionSnapshotExportArtifact,
		PermissionDistributionPublish,
		PermissionDistributionReadCurrent,
	}
}
