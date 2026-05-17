# Market Specification Delta

## Modified Requirements

### Requirement: Live Market Data Ingestion

The market service and workers MUST ingest mandi price data from a real configured source.

#### Scenario: Market data source configured

- GIVEN `DATA_GOV_IN_API_KEY` and either `MARKET_DATA_RESOURCE_ID` or
  `MARKET_DATA_API_URL` are configured
- WHEN the market sync worker runs
- THEN it fetches current mandi prices from the configured source
- AND posts normalized prices to the market service internal sync endpoint
- AND dashboard price rows reflect the latest stored sync data

#### Scenario: Market data source missing

- GIVEN live market env configuration is missing
- WHEN the worker attempts price sync
- THEN it fails the job with a clear configuration error
- AND the UI does not label seeded or stale development data as real-time live data
