#!/usr/bin/env python3
"""
Update IP ranges from ASN database and RIPE.

Downloads IP-to-ASN data and generates Go code for cloud provider IP ranges.
Also fetches additional ranges from RIPE database for providers not fully
covered by ASN data.
Minimizes overlapping/redundant ranges through CIDR merging.

Usage:
    python update_ip_ranges.py > ip_ranges_gen.go

Dependencies: Python 3.7+ (standard library only)
"""
from __future__ import annotations

import csv
import io
import ipaddress
import json
import re
import sys
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone

# URL for the IP-to-ASN database
IP_TO_ASN_URL = "https://github.com/iplocate/ip-address-databases/raw/refs/heads/main/ip-to-asn/ip-to-asn.csv.zip"

# Provider matching rules: map of provider name to regex patterns for ASN name field
# Patterns are matched case-insensitively against the 'name' column
PROVIDER_PATTERNS = {
    "ProviderAlibaba": [r"\bALIBABA\b", r"\bALIYUN\b"],
    "ProviderAWS": [r"\bAMAZON\b", r"\bAWS\b"],
    "ProviderAzure": [r"\bMICROSOFT\b", r"\bAZURE\b"],
    "ProviderCloudflare": [r"CLOUDFLARE"],
    "ProviderContabo": [r"\bCONTABO\b"],
    "ProviderDigitalOcean": [r"DIGITALOCEAN"],
    "ProviderGoogleCloud": [r"^GOOGLE\b"],
    "ProviderHetzner": [r"\bHETZNER\b"],
    "ProviderHostRoyale": [r"\bHOSTROYALE\b"],
    "ProviderIBMCloud": [r"\bSOFTLAYER\b", r"\bIBM\b"],
    "ProviderLeaseweb": [r"\bLEASEWEB\b"],
    "ProviderLinode": [r"\bLINODE\b", r"\bAKAMAI\b"],
    "ProviderOVH": [r"^OVH\b"],
    "ProviderOracleCloud": [r"\bORACLE\b"],
    "ProviderRackspace": [r"\bRACKSPACE\b"],
    "ProviderScaleway": [r"\bSCALEWAY\b", r"\bONLINE-NET\b"],
    "ProviderServersCom": [],  # Fetched from RIPE only
    "ProviderTencent": [r"\bTENCENT\b"],
    "ProviderVultr": [r"\bVULTR\b"],
}

# RIPE database sources for providers not fully covered by ASN data
# Format: (query_string, inverse_attribute, provider_const)
RIPE_SOURCES = [
    ("SERVERS-MNT", "mnt-by", "ProviderServersCom"),
    ("MNT-TISCALIFR", "mnt-by", "ProviderScaleway"),
    ("ONLINE-NET-MNT", "mnt-by", "ProviderScaleway"),
]

# Compile patterns
PROVIDER_MATCHERS = {
    provider: [re.compile(p, re.I) for p in patterns]
    for provider, patterns in PROVIDER_PATTERNS.items()
}


def download_and_extract_csv(url: str) -> str:
    """Download zip file and extract CSV content."""
    print(f"// Downloading from {url}", file=sys.stderr)

    request = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (compatible; isbot-updater/1.0)'}
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        zip_data = response.read()

    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        csv_files = [n for n in zf.namelist() if n.endswith('.csv')]
        if not csv_files:
            raise ValueError("No CSV file found in archive")

        with zf.open(csv_files[0]) as f:
            return f.read().decode('utf-8')


def ip_range_to_cidrs(start_ip: str, end_ip: str) -> list:
    """Convert an IP range (start-end) to a list of CIDR networks."""
    try:
        start = ipaddress.ip_address(start_ip)
        end = ipaddress.ip_address(end_ip)
        return list(ipaddress.summarize_address_range(start, end))
    except (ValueError, TypeError):
        return []


def fetch_ripe_ranges(query: str, inverse_attr: str, provider: str) -> list:
    """Fetch IP ranges from RIPE database using inverse search."""
    url = (
        f"https://rest.db.ripe.net/search.json?"
        f"query-string={query}&inverse-attribute={inverse_attr}"
        f"&type-filter=inetnum&flags=no-referenced&flags=no-irt&source=RIPE"
    )

    print(f"// Fetching RIPE data for {provider}: {query}", file=sys.stderr)

    request = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (compatible; isbot-updater/1.0)',
            'Accept': 'application/json',
        }
    )

    networks = []
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode('utf-8'))

        # Extract inetnum ranges from response
        objects = data.get('objects', {}).get('object', [])
        for obj in objects:
            primary_key = obj.get('primary-key', {}).get('attribute', [])
            for attr in primary_key:
                if attr.get('name') == 'inetnum':
                    # Format: "88.212.248.0 - 88.212.255.255"
                    range_str = attr.get('value', '').replace(' ', '')
                    if '-' in range_str:
                        start, end = range_str.split('-', 1)
                        cidrs = ip_range_to_cidrs(start, end)
                        networks.extend(cidrs)

        print(f"//   Found {len(networks)} ranges from RIPE for {provider}", file=sys.stderr)
    except Exception as e:
        print(f"// WARNING: Failed to fetch RIPE data for {provider}: {e}", file=sys.stderr)

    return networks


def classify_provider(name: str) -> str | None:
    """Return the provider constant if the ASN name matches, or None."""
    for provider, patterns in PROVIDER_MATCHERS.items():
        for pattern in patterns:
            if pattern.search(name):
                return provider
    return None


def parse_csv(csv_content: str) -> dict[str, list]:
    """Parse CSV and group networks by provider."""
    providers = defaultdict(list)

    reader = csv.reader(io.StringIO(csv_content))
    next(reader, None)  # skip header

    # Format: network,asn,country_code,name,org,domain
    for row in reader:
        if len(row) < 4:
            continue

        network_str = row[0]
        name = row[3]

        provider = classify_provider(name)
        if not provider:
            continue

        try:
            network = ipaddress.ip_network(network_str, strict=False)
            providers[provider].append(network)
        except (ValueError, TypeError):
            continue

    return providers


def merge_networks(networks: list) -> list:
    """Merge overlapping and adjacent networks into minimal set."""
    if not networks:
        return []

    ipv4 = sorted([n for n in networks if isinstance(n, ipaddress.IPv4Network)])
    ipv6 = sorted([n for n in networks if isinstance(n, ipaddress.IPv6Network)])

    def collapse(nets):
        if not nets:
            return []
        return list(ipaddress.collapse_addresses(nets))

    return collapse(ipv4) + collapse(ipv6)


def check_missing_providers(providers: dict) -> list[str]:
    """Check for providers with no matches and return warnings."""
    # Providers that are fetched from RIPE only (have no ASN patterns)
    ripe_only_providers = {src[2] for src in RIPE_SOURCES}

    warnings = []
    for provider, patterns in PROVIDER_PATTERNS.items():
        # Skip providers that are RIPE-only (empty patterns)
        if provider in ripe_only_providers and not patterns:
            continue
        if provider not in providers or len(providers[provider]) == 0:
            warnings.append(
                f"WARNING: No entries found for {provider} (patterns: {patterns}). "
                f"Provider may have been renamed."
            )
    return warnings


def generate_go_code(providers: dict) -> str:
    """Generate Go source code for IP ranges."""
    all_providers = sorted(providers.keys())

    lines = []
    lines.append("// Code generated by update_ip_ranges.py; DO NOT EDIT.")
    lines.append(f"// Source: {IP_TO_ASN_URL}")
    lines.append(f"// Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append("package isbot")
    lines.append("")
    lines.append('import (')
    lines.append('\t"net"')
    lines.append('\t"sync"')
    lines.append(')')
    lines.append("")

    lines.append("// CloudProvider represents a cloud/hosting provider")
    lines.append("type CloudProvider int")
    lines.append("")
    lines.append("const (")
    lines.append("\tProviderUnknown CloudProvider = iota")
    for provider in all_providers:
        lines.append(f"\t{provider}")
    lines.append(")")
    lines.append("")

    lines.append("func (p CloudProvider) String() string {")
    lines.append("\tswitch p {")
    for provider in all_providers:
        name = provider.replace("Provider", "")
        lines.append(f"\tcase {provider}:")
        lines.append(f'\t\treturn "{name}"')
    lines.append("\tdefault:")
    lines.append('\t\treturn "Unknown"')
    lines.append("\t}")
    lines.append("}")
    lines.append("")

    lines.append("type cloudIPRange struct {")
    lines.append("\tprovider CloudProvider")
    lines.append("\tnetwork  *net.IPNet")
    lines.append("}")
    lines.append("")
    lines.append("var (")
    lines.append("\tcloudRanges []cloudIPRange")
    lines.append("\tcloudOnce   sync.Once")
    lines.append(")")
    lines.append("")

    lines.append("func mustParseCIDR(cidr string, provider CloudProvider) cloudIPRange {")
    lines.append("\t_, network, err := net.ParseCIDR(cidr)")
    lines.append("\tif err != nil {")
    lines.append('\t\tpanic("invalid CIDR: " + cidr + ": " + err.Error())')
    lines.append("\t}")
    lines.append("\treturn cloudIPRange{provider: provider, network: network}")
    lines.append("}")
    lines.append("")

    lines.append("func initCloudRanges() {")
    lines.append("\tcloudRanges = []cloudIPRange{")

    for provider_const in sorted(providers.keys()):
        networks = providers[provider_const]
        if not networks:
            continue

        provider_name = provider_const.replace("Provider", "")
        lines.append(f"\t\t// {provider_name}")

        for network in networks:
            lines.append(f'\t\tmustParseCIDR("{network}", {provider_const}),')

    lines.append("\t}")
    lines.append("}")
    lines.append("")

    lines.append("// IPRangeProvider returns the cloud provider for an IP address.")
    lines.append("// Returns ProviderUnknown if not a known cloud provider IP.")
    lines.append("func IPRangeProvider(addr string) CloudProvider {")
    lines.append("\tcloudOnce.Do(initCloudRanges)")
    lines.append("")
    lines.append('\thost, _, err := net.SplitHostPort(addr)')
    lines.append("\tif err != nil {")
    lines.append("\t\thost = addr")
    lines.append("\t}")
    lines.append("")
    lines.append("\tip := net.ParseIP(host)")
    lines.append("\tif ip == nil {")
    lines.append("\t\treturn ProviderUnknown")
    lines.append("\t}")
    lines.append("")
    lines.append("\tfor _, r := range cloudRanges {")
    lines.append("\t\tif r.network.Contains(ip) {")
    lines.append("\t\t\treturn r.provider")
    lines.append("\t\t}")
    lines.append("\t}")
    lines.append("")
    lines.append("\treturn ProviderUnknown")
    lines.append("}")
    lines.append("")

    lines.append("// IsCloudProvider returns true if the IP belongs to any known cloud provider.")
    lines.append("func IsCloudProvider(addr string) bool {")
    lines.append("\treturn IPRangeProvider(addr) != ProviderUnknown")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


def print_stats(providers: dict, merged_providers: dict):
    """Print statistics about the processing."""
    print("// Processing statistics:", file=sys.stderr)
    total_before = sum(len(v) for v in providers.values())
    total_after = sum(len(v) for v in merged_providers.values())

    for provider_const in sorted(providers.keys()):
        before = len(providers[provider_const])
        after = len(merged_providers.get(provider_const, []))
        name = provider_const.replace("Provider", "")
        print(f"//   {name}: {before} -> {after} ranges", file=sys.stderr)

    if total_before > 0:
        reduction = 100 - (total_after / total_before * 100)
        print(f"// Total: {total_before} -> {total_after} ranges ({reduction:.1f}% reduction)", file=sys.stderr)
    else:
        print("// No matching ranges found", file=sys.stderr)


def main():
    csv_content = download_and_extract_csv(IP_TO_ASN_URL)
    providers = parse_csv(csv_content)

    # Fetch additional ranges from RIPE
    for query, inverse_attr, provider in RIPE_SOURCES:
        ripe_networks = fetch_ripe_ranges(query, inverse_attr, provider)
        if provider not in providers:
            providers[provider] = []
        providers[provider].extend(ripe_networks)

    # Check for missing providers and warn
    warnings = check_missing_providers(providers)
    for warning in warnings:
        print(f"// {warning}", file=sys.stderr)

    if warnings:
        print("//", file=sys.stderr)
        print("// ACTION REQUIRED: Update PROVIDER_PATTERNS for renamed providers", file=sys.stderr)
        sys.exit(1)

    # Merge networks per provider
    merged_providers = {}
    for provider_const, networks in providers.items():
        merged_providers[provider_const] = merge_networks(networks)

    print_stats(providers, merged_providers)

    go_code = generate_go_code(merged_providers)
    print(go_code)


if __name__ == "__main__":
    main()
