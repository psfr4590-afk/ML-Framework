$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Target = Join-Path $Root "third_party\llama.cpp"
$Repo = "https://github.com/ggml-org/llama.cpp.git"
$Tag = "b10516"
$Commit = "b95502b"

Write-Host "`n=== LLAMA.CPP BOOTSTRAP ===" -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $Target ".git"))) {
    if (Test-Path $Target) {
        Remove-Item $Target -Recurse -Force
    }

    New-Item -ItemType Directory -Force -Path (Split-Path $Target) | Out-Null

    git clone --depth 1 --branch $Tag $Repo $Target
}

Set-Location $Target

$Actual = (git rev-parse HEAD).Trim()

if (-not $Actual.StartsWith($Commit)) {
    throw "llama.cpp pin mismatch: expected $Commit got $Actual"
}

if (-not (Test-Path "convert_hf_to_gguf.py")) {
    throw "Missing convert_hf_to_gguf.py"
}

$Build = "build-model-lab"

Write-Host "`n=== CONFIGURING CMAKE ===" -ForegroundColor Cyan

$Args = @(
    "-S", ".",
    "-B", $Build,
    "-DCMAKE_BUILD_TYPE=Release",
    "-DBUILD_SHARED_LIBS=OFF",
    "-DGGML_NATIVE=OFF",
    "-DGGML_OPENMP=OFF",
    "-DGGML_LLAMAFILE=OFF",
    "-DLLAMA_CURL=OFF",
    "-DLLAMA_BUILD_TESTS=OFF",
    "-DLLAMA_BUILD_SERVER=ON",
    "-DLLAMA_BUILD_CLI=ON",
    "-DLLAMA_BUILD_TOOLS=ON",
    "-DLLAMA_BUILD_EXAMPLES=ON"
)

cmake @Args

Write-Host "`n=== BUILDING NATIVE ARTIFACTS ===" -ForegroundColor Cyan

cmake --build $Build `
    --config Release `
    --target llama-quantize llama-cli `
    --parallel

$Quant = Get-ChildItem -Path $Build `
    -Recurse `
    -File `
    -Filter "llama-quantize.exe" |
    Select-Object -First 1

$App = Get-ChildItem -Path $Build `
    -Recurse `
    -File `
    -Filter "llama.exe" |
    Select-Object -First 1

if (-not $Quant) {
    throw "llama-quantize.exe was not built"
}

if (-not $App) {
    throw "llama.exe was not built"
}

Write-Host "`n=== LLAMA.CPP READY ===" -ForegroundColor Green
Write-Host "  converter: $Target\convert_hf_to_gguf.py"
Write-Host "  quantizer: $($Quant.FullName)"
Write-Host "  app:       $($App.FullName)"
