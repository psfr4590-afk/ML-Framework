$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Target = Join-Path $Root "third_party\llama.cpp"
$Repo = "https://github.com/ggml-org/llama.cpp.git"
$Tag = "b10516"
$Commit = "b95502b"

if (-not (Test-Path (Join-Path $Target ".git"))) {
    if (Test-Path $Target) { Remove-Item $Target -Recurse -Force }
    New-Item -ItemType Directory -Force -Path (Split-Path $Target) | Out-Null
    git clone --depth 1 --branch $Tag $Repo $Target
}

Set-Location $Target
$Actual = (git rev-parse HEAD).Trim()
if (-not $Actual.StartsWith($Commit)) { throw "llama.cpp pin mismatch: expected $Commit got $Actual" }
if (-not (Test-Path "convert_hf_to_gguf.py")) { throw "Missing convert_hf_to_gguf.py" }

$Build = "build-model-lab"
$Args = @(
    "-S", ".", "-B", $Build,
    "-DCMAKE_BUILD_TYPE=Release",
    "-DBUILD_SHARED_LIBS=OFF",
    "-DGGML_NATIVE=OFF",
    "-DGGML_OPENMP=OFF",
    "-DGGML_LLAMAFILE=OFF",
    "-DLLAMA_CURL=OFF",
    "-DLLAMA_BUILD_TESTS=OFF",
    "-DLLAMA_BUILD_SERVER=OFF",
    "-DLLAMA_BUILD_APP=OFF",
    "-DLLAMA_BUILD_TOOLS=ON",
    "-DLLAMA_BUILD_EXAMPLES=ON"
)

cmake @Args
cmake --build $Build --config Release --target llama-quantize --parallel

$Quant = Get-ChildItem -Path $Build -Recurse -File -Filter "llama-quantize.exe" |
    Select-Object -First 1

if (-not $Quant) { throw "llama-quantize was not built" }

Write-Host "llama.cpp ready at $Target"
Write-Host "  converter: $Target\convert_hf_to_gguf.py"
Write-Host "  quantizer: $($Quant.FullName)"
