# Implementation Tasks: No-Mock Model, Data, Integration, and Verification Readiness

## ID: no-mock-model-data-readiness
## Status: Planned

- [ ] 1. Finish and commit the current auth-refresh + Soft Craft UI change.
- [ ] 2. Run deep Playwright verification across auth and every dashboard feature page.
- [ ] 3. Create a mock/stub/in-memory inventory mapped to OpenSpec requirements.
- [ ] 4. Research authoritative dataset/API sources and current library training patterns.
- [ ] 5. Add dataset directory conventions and `.gitignore` rules for raw/processed data and model artifacts.
- [ ] 6. Add crop recommendation training script with metadata-emitting artifact output.
- [ ] 7. Add yield prediction training script with metadata-emitting artifact output.
- [ ] 8. Add fertilizer recommendation training script with metadata-emitting artifact output.
- [ ] 9. Add vision preprocessing/training entrypoints and artifact metadata conventions.
- [ ] 10. Change ML services to require real artifacts by default and report readiness failures clearly.
- [ ] 11. Keep explicit local fallback mode available only through env flags for development.
- [ ] 12. Wire farm weather to OpenWeatherMap using `OPENWEATHERMAP_API_KEY` and cache settings.
- [ ] 13. Wire market sync to env-configured data.gov.in/AGMARKNET endpoint/key.
- [ ] 14. Add tests for training utility validation, artifact metadata, and service readiness.
- [ ] 15. Add Playwright tests or scripts for critical UI feature flows.
- [ ] 16. Write full README.md with setup, env, datasets, training, Docker, tests, and operations.
- [ ] 17. Run all verification commands and Docker Compose startup.
- [ ] 18. Produce and commit OpenSpec implementation comparison notes.
