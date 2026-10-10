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
    if ($LASTEXITCODE -ne 0) {
        throw "llama.cpp clone failed with exit code $LASTEXITCODE"
    }
}

Set-Location $Target

$Actual = git rev-parse HEAD
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read the llama.cpp checkout commit"
}
$Actual = $Actual.Trim()

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
    "-DLLAMA_BUILD_SERVER=OFF",
    "-DLLAMA_BUILD_TOOLS=ON",
    "-DLLAMA_BUILD_EXAMPLES=ON"
)

cmake @Args
if ($LASTEXITCODE -ne 0) {
    throw "CMake configuration failed with exit code $LASTEXITCODE"
}

Write-Host "`n=== BUILDING LLAMA-QUANTIZE ===" -ForegroundColor Cyan

# Clean the generated build outputs first so a failed build cannot be
# mistaken for success merely because an older executable is still present.
cmake --build $Build --config Release --target llama-quantize --clean-first --parallel 2
if ($LASTEXITCODE -ne 0) {
    throw "llama-quantize build failed with exit code $LASTEXITCODE"
}

Write-Host "`n=== BUILDING LLAMA-CLI ===" -ForegroundColor Cyan

# Build the targets separately. This also avoids relying on a multi-target
# Visual Studio/MSBuild invocation that can fail to resolve a target project.
cmake --build $Build --config Release --target llama-cli --parallel 2
if ($LASTEXITCODE -ne 0) {
    throw "llama-cli build failed with exit code $LASTEXITCODE"
}

$Quant = Get-ChildItem -Path $Build `
    -Recurse `
    -File `
    -Filter "llama-quantize.exe" |
    Select-Object -First 1

$Cli = Get-ChildItem -Path $Build `
    -Recurse `
    -File `
    -Filter "llama-cli.exe" |
    Select-Object -First 1

if (-not $Quant) {
    throw "llama-quantize.exe was not produced by the successful build"
}

if (-not $Cli) {
    throw "llama-cli.exe was not produced by the successful build"
}

Write-Host "`n=== LLAMA.CPP READY ===" -ForegroundColor Green
Write-Host "  converter: $Target\convert_hf_to_gguf.py"
Write-Host "  quantizer: $($Quant.FullName)"
Write-Host "  cli:       $($Cli.FullName)"
