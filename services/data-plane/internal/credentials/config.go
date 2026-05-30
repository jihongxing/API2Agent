package credentials

import (
	"encoding/json"
	"fmt"
	"os"
)

type ConfigFile struct {
	Credentials []CredentialDefinition `json:"credentials"`
}

func LoadConfigFile(path string) ([]CredentialDefinition, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read credential config: %w", err)
	}
	var config ConfigFile
	if err := json.Unmarshal(data, &config); err != nil {
		var list []CredentialDefinition
		if listErr := json.Unmarshal(data, &list); listErr == nil {
			return list, nil
		}
		return nil, fmt.Errorf("decode credential config: %w", err)
	}
	return config.Credentials, nil
}
