# Farm Specification Delta

## Modified Requirements

### Requirement: Weather Integration

The farm service MUST fetch real weather data from OpenWeatherMap when a key is provided.

#### Scenario: Weather key configured

- GIVEN `OPENWEATHERMAP_API_KEY` is configured
- WHEN `GET /farms/:id/weather` is called for a farm owned by the user
- THEN the service requests weather for the farm centroid from OpenWeatherMap
- AND caches the normalized result according to `WEATHER_CACHE_TTL`

#### Scenario: Weather key missing

- GIVEN `OPENWEATHERMAP_API_KEY` is not configured
- WHEN real weather is required
- THEN the service returns a clear dependency/configuration error instead of pretending
  stub weather is real
