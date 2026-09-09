param([switch]$IncludeMachineChecks,[switch]$NoDoctor)
$ErrorActionPreference="Stop"
$Root=Split-Path -Parent $PSScriptRoot
Set-Location $Root
if(-not $NoDoctor){python .\run_pipeline.py --doctor}
python -m pytest -q
python -m compileall -q .\ui .\command_center .\pipeline .\run_pipeline.py .\run_command_center.py .\launch.py
if($IncludeMachineChecks){python -m pytest -q .\tests\model_lab\test_machine_environment.py}
