# Foundry Local Inference Workload

Edge LLM inference benchmark built on
[Microsoft Foundry Local](https://learn.microsoft.com/azure/ai-foundry/foundry-local/).
It uses the Foundry Local 2.0 SDK, ensures a model is cached (default
`qwen2.5-0.5b`), runs a single-prompt inference, and reports the end-to-end
runtime.

## What HOBL sets up

- A per-scenario .NET 8 SDK under `mac_foundrylocal_resources/foundrylocal_app/.dotnet`
- `Microsoft.AI.Foundry.Local` 2.0.1 and its `osx-arm64` native runtime
- A model downloaded on demand through the SDK

## Run it standalone

```zsh
zsh ./mac_foundrylocal_resources/mac_foundrylocal_prep.sh
./mac_foundrylocal_resources/foundrylocal_app/.dotnet/dotnet \
    ./mac_foundrylocal_resources/foundrylocal_app/publish/FoundryLocalWorkload.dll \
    run qwen2.5-0.5b "What is the meaning of life?"
```

## Notes

- The Foundry Local SDK is pinned to version 2.0.1.
- Apple Silicon (`arm64`) is required.
- Default: 1 loop.
- First run downloads the model; the HOBL teardown removes it afterward.
