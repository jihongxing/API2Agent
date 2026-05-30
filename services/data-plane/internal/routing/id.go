package routing

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
)

func NewID(prefix string) string {
	var buf [8]byte
	if _, err := rand.Read(buf[:]); err != nil {
		return fmt.Sprintf("%s_fallback", prefix)
	}
	return fmt.Sprintf("%s_%s", prefix, hex.EncodeToString(buf[:]))
}
