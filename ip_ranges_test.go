package isbot

import "testing"

func TestIPRangeProvider(t *testing.T) {
	tests := []struct {
		name     string
		ip       string
		expected CloudProvider
	}{
		// AWS tests
		{
			name:     "AWS eu-central-1 IP (3.67.103.209)",
			ip:       "3.67.103.209",
			expected: ProviderAWS,
		},
		{
			name:     "AWS eu-central-1 IP with port",
			ip:       "3.67.103.209:8080",
			expected: ProviderAWS,
		},
		{
			name:     "AWS 3.64.0.1",
			ip:       "3.64.0.1",
			expected: ProviderAWS,
		},
		{
			name:     "AWS 3.67.255.255",
			ip:       "3.67.255.255",
			expected: ProviderAWS,
		},

		// Hetzner tests
		{
			name:     "Hetzner IP",
			ip:       "5.78.100.50",
			expected: ProviderHetzner,
		},
		{
			name:     "Hetzner IP 2",
			ip:       "65.108.50.100",
			expected: ProviderHetzner,
		},

		// DigitalOcean tests
		{
			name:     "DigitalOcean IP",
			ip:       "24.144.100.50",
			expected: ProviderDigitalOcean,
		},

		// Google Cloud tests
		{
			name:     "Google Cloud IP",
			ip:       "35.199.50.100",
			expected: ProviderGoogleCloud,
		},

		// Unknown tests
		{
			name:     "Private IP",
			ip:       "192.168.1.1",
			expected: ProviderUnknown,
		},
		{
			name:     "Localhost",
			ip:       "127.0.0.1",
			expected: ProviderUnknown,
		},
		{
			name:     "Empty string",
			ip:       "",
			expected: ProviderUnknown,
		},
		{
			name:     "Invalid IP",
			ip:       "not-an-ip",
			expected: ProviderUnknown,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := IPRangeProvider(tt.ip)
			if result != tt.expected {
				t.Errorf("IPRangeProvider(%q) = %v, want %v", tt.ip, result, tt.expected)
			}
		})
	}
}

func TestIsCloudProvider(t *testing.T) {
	tests := []struct {
		name     string
		ip       string
		expected bool
	}{
		{"AWS IP", "3.67.103.209", true},
		{"Hetzner IP", "5.78.100.50", true},
		{"Private IP", "192.168.1.1", false},
		{"Empty", "", false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := IsCloudProvider(tt.ip)
			if result != tt.expected {
				t.Errorf("IsCloudProvider(%q) = %v, want %v", tt.ip, result, tt.expected)
			}
		})
	}
}

func TestCloudProviderString(t *testing.T) {
	tests := []struct {
		provider CloudProvider
		expected string
	}{
		{ProviderUnknown, "Unknown"},
		{ProviderAWS, "AWS"},
		{ProviderDigitalOcean, "DigitalOcean"},
		{ProviderGoogleCloud, "GoogleCloud"},
		{ProviderHetzner, "Hetzner"},
	}

	for _, tt := range tests {
		t.Run(tt.expected, func(t *testing.T) {
			if tt.provider.String() != tt.expected {
				t.Errorf("CloudProvider.String() = %v, want %v", tt.provider.String(), tt.expected)
			}
		})
	}
}
