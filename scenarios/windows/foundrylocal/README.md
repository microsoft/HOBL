# Foundry Local Inference Workload

Edge LLM inference benchmark built on
[Microsoft Foundry Local](https://learn.microsoft.com/azure/ai-foundry/foundry-local/).
It uses the Foundry Local 2.0 SDK, ensures a model is cached (default
`qwen2.5-0.5b`), runs a single-prompt inference, and reports the
end-to-end runtime.

## What HOBL sets up (from `foundrylocal_resources/*.ps1`)

- .NET 8 SDK (`Microsoft.DotNet.SDK.8` via winget)
- `Microsoft.AI.Foundry.Local` 2.0.1 and its native runtime (NuGet)
- Model downloaded on demand through the SDK (cached locally)

## Run it standalone (Windows)

```powershell
pwsh .\foundrylocal_resources\foundrylocal_prep.ps1
dotnet .\foundrylocal_resources\foundrylocal_app\publish\FoundryLocalWorkload.dll `
    run qwen2.5-0.5b "What is the meaning of life?"
```

## Notes

- The Foundry Local SDK is pinned to version 2.0.1.
- Default: 1 loop. Works on x64 and ARM64.
- First run downloads the model; the HOBL teardown removes it afterward.
