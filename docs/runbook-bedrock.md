# Runbook – Bedrock readiness

**Maintainer‑only steps**

1. **AWS Support case** – An open case `179171601300238` must be resolved before production use of Bedrock. Keep it monitored.
2. **Playground sanity check** – After case approval, open the Bedrock Playground (console) with the model you intend to use and run a single request to ensure the service is reachable.
3. **Anthropic use‑case form (optional)** – If you plan to use Claude models, submit the [Anthropic use‑case form](https://docs.anthropic.com/claude/use-case-form) with your intended workload description.
4. **Set BedrockModelId** – In `samconfig.toml` add a **commented** example (do *not* commit a real ID):
   ```toml
   # BEDROCK_MODEL_ID=global.amazon.nova-2-lite-v1:0
   ```
   The actual value will be injected via the CI environment during deployment.
5. **Deploy** – Merge the PR to `main` or run a manual deployment:
   ```bash
   sam deploy --profile thirst
   ```
6. **Verify** – After deployment, call the live endpoint:
   ```bash
   curl -X POST https://<api-url>/explain -d '{"text":"test"}'
   ```
   The JSON response should contain `"source":"bedrock"` and no `note` indicating an error.

**Reason‑code table (handler `/explain`)**
| Reason code (AWS) | Client note |
|------------------|-------------|
| AccessDeniedException / ValidationException | `bedrock_not_authorized` |
| ThrottlingException | `bedrock_throttled` |
| ConnectTimeoutError / ReadTimeoutError / EndpointConnectionError | `bedrock_timeout` |
| any other error | `agent_failed` |

**Changelog** – add entry **D38** to `AGENTS.md` describing the new mapping and the `/parse-sentence` endpoint.

*No real BedrockModelId is stored in the repo; only the commented example above.*
