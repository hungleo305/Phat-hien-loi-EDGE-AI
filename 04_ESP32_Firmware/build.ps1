# Build only. This script never flashes or starts the hardware.
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$datnRoot = Split-Path (Split-Path $projectRoot -Parent) -Parent
$buildRoot = Join-Path $datnRoot 'Cong_cu_phat_trien/outputs/esp32_build'
$idfRoot = 'C:/Espressif/frameworks/esp-idf-v5.3.5'
$pythonExe = 'C:/Espressif/python_env/idf5.3_py3.12_env/Scripts/python.exe'
$cmakeExe = 'C:/Espressif/tools/cmake/3.30.2/bin/cmake.exe'
$ninjaExe = 'C:/Espressif/tools/ninja/1.12.1/ninja.exe'
$compilerDir = 'C:/Espressif/tools/xtensa-esp-elf/esp-13.2.0_20250707/xtensa-esp-elf/bin'
$env:IDF_PATH = $idfRoot
$env:IDF_TOOLS_PATH = 'C:/Espressif'
$env:ESP_ROM_ELF_DIR = 'C:/Espressif/tools/esp-rom-elfs/20240305/'
$env:IDF_PYTHON_ENV_PATH = Split-Path (Split-Path $pythonExe -Parent) -Parent
$env:PATH = "$compilerDir;$(Split-Path $cmakeExe);$(Split-Path $ninjaExe);$(Split-Path $pythonExe);$env:PATH"

& $cmakeExe -S $projectRoot -B $buildRoot -G Ninja `
    "-DPYTHON=$pythonExe" '-DIDF_TARGET=esp32' '-DCCACHE_ENABLE=0' `
    "-DSDKCONFIG=$projectRoot/sdkconfig"
if ($LASTEXITCODE -ne 0) { throw 'ESP-IDF configure failed.' }
& $ninjaExe -C $buildRoot
if ($LASTEXITCODE -ne 0) { throw 'ESP-IDF build failed.' }
Write-Host "Firmware: $buildRoot/ESP32_Firmware.bin"
