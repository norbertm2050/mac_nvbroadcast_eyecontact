$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot)
$python = if ($env:EYE_BUILD_PYTHON) { $env:EYE_BUILD_PYTHON } else { 'python' }
$ErrorActionPreference = 'Continue'
& $python -m PyInstaller --noconfirm --clean --onedir --windowed --name RemoteEyeContact --icon (Join-Path (Get-Location) 'assets/AppIcon.ico') --paths src --collect-all av --collect-all pyvirtualcam --exclude-module mac_camera --distpath build/package --workpath build/pyinstaller --specpath build src/backend.py
$buildExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($buildExit -ne 0) { throw 'PyInstaller failed' }
$dest = 'build/package/RemoteEyeContact'
if (!(Test-Path 'vendor/mediamtx.exe')) { throw 'Run scripts/fetch-mediamtx.py first.' }
Copy-Item vendor/mediamtx.exe $dest
Copy-Item assets/AppIcon.ico $dest
New-Item "$dest/assets" -ItemType Directory -Force | Out-Null
Copy-Item assets/icon.png "$dest/assets/"
Copy-Item scripts/configure-firewall.ps1 $dest
Copy-Item LICENSE,THIRD_PARTY_NOTICES.md,README.md,CHANGELOG.md $dest
Copy-Item docs "$dest/docs" -Recurse -Force
Copy-Item licenses "$dest/licenses" -Recurse -Force
New-Item dist -ItemType Directory -Force | Out-Null
Compress-Archive -Path "$dest/*" -DestinationPath dist/Remote-Eye-Contact-Windows-x64.zip -Force
