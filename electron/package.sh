#!/bin/bash
# JCodex 模版打包：Electron.app 复制改名 + PyInstaller 后端 + ad-hoc 签名 + DMG
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="JCodex"
ELECTRON_APP="node_modules/electron/dist/Electron.app"
DIST="dist"
APP="$DIST/$APP_NAME.app"
DMG="$DIST/$APP_NAME.dmg"
STAGING="staging"
BACKEND_SRC="dist-server/jcodex-server"

echo "==> [1/7] 构建后端 (PyInstaller)"
python3.11 -m PyInstaller --noconfirm --clean --workpath build-server --distpath dist-server jcodex-server.spec

echo "==> [2/7] 复制 Electron.app 模板"
rm -rf "$APP" "$STAGING" "$DMG"
ditto "$ELECTRON_APP" "$APP"
mv "$APP/Contents/MacOS/Electron" "$APP/Contents/MacOS/$APP_NAME"

echo "==> [3/7] 植入前端与后端"
mkdir -p "$APP/Contents/Resources/app" "$APP/Contents/Resources/backend"
cp main.js package.json "$APP/Contents/Resources/app/"
cp build/icon.icns "$APP/Contents/Resources/icon.icns"
cp -R "$BACKEND_SRC" "$APP/Contents/Resources/backend/jcodex-server"
chmod +x "$APP/Contents/MacOS/$APP_NAME"
chmod +x "$APP/Contents/Resources/backend/jcodex-server/jcodex-server"

echo "==> [4/7] 精简 Electron 语言包（只保留 en/zh_CN）"
find "$APP/Contents/Resources" -maxdepth 1 -name "*.lproj" \
  ! -name "en.lproj" ! -name "zh_CN.lproj" -exec rm -rf {} +

echo "==> [5/7] 元数据"
/usr/libexec/PlistBuddy -c "Set :CFBundleName $APP_NAME" \
  -c "Set :CFBundleDisplayName $APP_NAME" \
  -c "Set :CFBundleIdentifier com.jcodex.desktop" \
  -c "Set :CFBundleExecutable $APP_NAME" \
  -c "Set :CFBundleIconFile icon.icns" \
  -c "Set :CFBundleShortVersionString 1.0.0" \
  -c "Set :CFBundleVersion 1.0.0" \
  "$APP/Contents/Info.plist"

echo "==> [6/7] ad-hoc 签名"
codesign --force --sign - --identifier com.jcodex.desktop --deep "$APP"

echo "==> [7/7] 生成 DMG"
mkdir -p "$STAGING"
ditto "$APP" "$STAGING/$APP_NAME.app"
ln -s /Applications "$STAGING/Applications"
hdiutil create -volname "$APP_NAME" -srcfolder "$STAGING" -ov -format UDZO "$DMG"
hdiutil verify "$DMG"
rm -rf "$STAGING"
echo "==> 完成: $DMG"
du -sh "$APP" "$DMG"
