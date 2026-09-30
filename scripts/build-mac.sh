#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
"$PYTHON" scripts/sanitize-sysconfig.py
"$PYTHON" -m PyInstaller --noconfirm --clean --onedir --name eye-backend \
  --paths build/sanitized --paths src --collect-all av --collect-all pyvirtualcam --exclude-module tkinter \
  --exclude-module windows_app --exclude-module win_receiver --exclude-module win_sender \
  --distpath build/backend --workpath build/pyinstaller --specpath build src/backend.py
APP="dist/Remote Eye Contact.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
rm -rf "$APP/Contents/Resources/Backend"
cp -R build/backend/eye-backend "$APP/Contents/Resources/Backend"
xcrun swiftc app/MenuApp.swift -O -o "$APP/Contents/MacOS/RemoteEyeContact" -framework AppKit -framework AVFoundation
"$PYTHON" - "$APP/Contents/Info.plist" <<'PY'
import plistlib,sys
with open(sys.argv[1],'wb') as f:
    plistlib.dump(dict(CFBundleIdentifier='io.github.norbertm2050.remote-eye-contact',CFBundleName='Remote Eye Contact',CFBundleExecutable='RemoteEyeContact',CFBundlePackageType='APPL',CFBundleShortVersionString='1.1.1',CFBundleVersion='3',CFBundleIconFile='AppIcon',LSUIElement=True,LSMinimumSystemVersion='14.0',NSCameraUseContinuityCameraDeviceType=True,NSCameraUsageDescription='将摄像头画面发送至你配置的 Windows NVIDIA Broadcast 进行眼神矫正，再输出到本机虚拟摄像头。'),f)
PY
mkdir -p "$APP/Contents/Resources/assets"
cp assets/icon.png "$APP/Contents/Resources/assets/"
cp assets/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"
cp LICENSE README.md CHANGELOG.md THIRD_PARTY_NOTICES.md "$APP/Contents/Resources/"
cp -R docs "$APP/Contents/Resources/"
cp -R licenses "$APP/Contents/Resources/"
codesign --force --deep --sign "${CODESIGN_IDENTITY:--}" "$APP"
codesign --verify --deep --strict "$APP"
ditto -c -k --sequesterRsrc --keepParent "$APP" dist/Remote-Eye-Contact-macOS-arm64.zip
