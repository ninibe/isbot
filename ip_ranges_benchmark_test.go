package isbot

import (
	"testing"
)

// BenchmarkIPRangeProvider_CloudIP benchmarks looking up a known cloud provider IP
func BenchmarkIPRangeProvider_CloudIP(b *testing.B) {
	// Ensure ranges are initialized before benchmark
	_ = IPRangeProvider("3.67.103.209")

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		IPRangeProvider("3.67.103.209")
	}
}

// BenchmarkIPRangeProvider_NonCloudIP benchmarks looking up a non-cloud IP (worst case - checks all ranges)
func BenchmarkIPRangeProvider_NonCloudIP(b *testing.B) {
	// Ensure ranges are initialized before benchmark
	_ = IPRangeProvider("192.168.1.1")

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		IPRangeProvider("192.168.1.1")
	}
}

// BenchmarkIPRangeProvider_WithPort benchmarks IP with port (common case from RemoteAddr)
func BenchmarkIPRangeProvider_WithPort(b *testing.B) {
	// Ensure ranges are initialized before benchmark
	_ = IPRangeProvider("3.67.103.209:8080")

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		IPRangeProvider("3.67.103.209:8080")
	}
}

// BenchmarkIsCloudProvider benchmarks the boolean check
func BenchmarkIsCloudProvider(b *testing.B) {
	// Ensure ranges are initialized before benchmark
	_ = IsCloudProvider("3.67.103.209")

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		IsCloudProvider("3.67.103.209")
	}
}

// BenchmarkIsCloudProvider_NonCloud benchmarks checking a non-cloud IP
func BenchmarkIsCloudProvider_NonCloud(b *testing.B) {
	// Ensure ranges are initialized before benchmark
	_ = IsCloudProvider("192.168.1.1")

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		IsCloudProvider("192.168.1.1")
	}
}

// BenchmarkIPRangeProvider_VariousProviders tests lookup across different providers
func BenchmarkIPRangeProvider_VariousProviders(b *testing.B) {
	ips := []string{
		"3.67.103.209",   // AWS
		"20.50.100.50",   // Azure
		"35.199.50.100",  // Google
		"24.144.100.50",  // DigitalOcean
		"5.78.100.50",    // Hetzner
		"192.168.1.1",    // Non-cloud
	}

	// Ensure ranges are initialized
	_ = IPRangeProvider(ips[0])

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		for _, ip := range ips {
			IPRangeProvider(ip)
		}
	}
}

