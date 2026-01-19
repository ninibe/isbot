package isbot

var providerToResult = map[CloudProvider]Result{
	ProviderAWS:          BotRangeAWS,
	ProviderAlibaba:      BotRangeAlibaba,
	ProviderAzure:        BotRangeAzure,
	ProviderCloudflare:   BotRangeCloudflare,
	ProviderContabo:      BotRangeContabo,
	ProviderDigitalOcean: BotRangeDigitalOcean,
	ProviderGoogleCloud:  BotRangeGoogleCloud,
	ProviderHetzner:      BotRangeHetzner,
	ProviderIBMCloud:     BotRangeIBMCloud,
	ProviderLeaseweb:     BotRangeLeaseweb,
	ProviderLinode:       BotRangeLinode,
	ProviderOVH:          BotRangeOVH,
	ProviderOracleCloud:  BotRangeOracleCloud,
	ProviderRackspace:    BotRangeRackspace,
	ProviderScaleway:     BotRangeScaleway,
	ProviderServersCom:   BotRangeServersCom,
	ProviderTencent:      BotRangeTencent,
	ProviderVultr:        BotRangeVultr,
}

// IPRange checks if this IP address is from a range that should normally never
// send browser requests, such as AWS and other cloud providers.
func IPRange(addr string) Result {
	if result, ok := providerToResult[IPRangeProvider(addr)]; ok {
		return result
	}
	return NoBotNoMatch
}
