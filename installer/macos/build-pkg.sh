#!/bin/bash
# build-pkg.sh — Builds a macOS .pkg installer for Book Editor
# Usage: bash installer/macos/build-pkg.sh <VERSION>
# Expects: dist/BookEditor.app to exist (output of flet pack)
# Produces: dist/BookEditor-macOS-<VERSION>.pkg
set -euo pipefail

VERSION="${1:?Usage: build-pkg.sh <VERSION>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

APP_SOURCE="$REPO_ROOT/dist/BookEditor.app"
PKG_ROOT="$REPO_ROOT/build/pkg-root"
SCRIPTS_DIR="$SCRIPT_DIR/scripts"
COMPONENT_PKG="$REPO_ROOT/build/BookEditor-component.pkg"
BUILD_DIR="$REPO_ROOT/build"
FINAL_PKG="$REPO_ROOT/dist/BookEditor-macOS-${VERSION}.pkg"

echo "==> Building Book Editor macOS PKG v${VERSION}"

# ── Validate inputs ───────────────────────────────────────────────────────────
if [ ! -d "$APP_SOURCE" ]; then
  echo "ERROR: $APP_SOURCE not found. Run 'flet pack' first."
  exit 1
fi

if [ ! -f "$SCRIPTS_DIR/postinstall" ]; then
  echo "ERROR: postinstall script not found at $SCRIPTS_DIR/postinstall"
  exit 1
fi

# ── Prepare staging directory ─────────────────────────────────────────────────
echo "==> Staging app bundle..."
rm -rf "$PKG_ROOT"
mkdir -p "$PKG_ROOT/Applications"
cp -R "$APP_SOURCE" "$PKG_ROOT/Applications/BookEditor.app"

chmod +x "$SCRIPTS_DIR/postinstall"

# ── Build the component pkg ───────────────────────────────────────────────────
echo "==> Running pkgbuild..."
pkgbuild \
  --root "$PKG_ROOT" \
  --identifier "com.bookeditor.app" \
  --version "$VERSION" \
  --install-location "/" \
  --scripts "$SCRIPTS_DIR" \
  "$COMPONENT_PKG"

# ── Generate distribution XML ─────────────────────────────────────────────────
DIST_XML="$BUILD_DIR/distribution.xml"
cat > "$DIST_XML" << DISTXML
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>Book Editor ${VERSION}</title>
    <organization>com.bookeditor</organization>
    <domains enable_localSystem="true"/>
    <options customize="never" require-scripts="true" hostArchitectures="x86_64,arm64"/>
    <welcome file="welcome.html" mime-type="text/html"/>
    <license file="LICENSE" mime-type="text/plain"/>
    <conclusion file="conclusion.html" mime-type="text/html"/>
    <choices-outline>
        <line choice="default">
            <line choice="com.bookeditor.app"/>
        </line>
    </choices-outline>
    <choice id="default"/>
    <choice id="com.bookeditor.app" visible="false">
        <pkg-ref id="com.bookeditor.app"/>
    </choice>
    <pkg-ref id="com.bookeditor.app" version="${VERSION}" onConclusion="none">BookEditor-component.pkg</pkg-ref>
</installer-gui-script>
DISTXML

# ── Assemble PKG resources ────────────────────────────────────────────────────
RESOURCES_DIR="$BUILD_DIR/pkg-resources"
mkdir -p "$RESOURCES_DIR"

cat > "$RESOURCES_DIR/welcome.html" << 'WELCOME'
<!DOCTYPE html>
<html><body>
<h2>Welcome to Book Editor</h2>
<p>This installer will install <strong>Book Editor</strong> into your Applications folder.</p>
<p>It will also install <strong>Pandoc</strong>, <strong>BasicTeX</strong>, and ensure
<strong>Git</strong> is available — these are required for PDF export and GitHub sync.</p>
<p>An internet connection is required during installation.</p>
</body></html>
WELCOME

cat > "$RESOURCES_DIR/conclusion.html" << 'CONCLUSION'
<!DOCTYPE html>
<html><body>
<h2>Installation Complete</h2>
<p><strong>Book Editor</strong> has been installed to your Applications folder.</p>
<p>Pandoc, BasicTeX, and Git have been set up. If any dependency installation
messages appeared, they may take a moment to complete in the background.</p>
<p>Launch <strong>Book Editor</strong> from your Applications folder or Launchpad.</p>
</body></html>
CONCLUSION

cp "$REPO_ROOT/LICENSE" "$RESOURCES_DIR/LICENSE"

# ── Build the final distribution pkg ─────────────────────────────────────────
echo "==> Running productbuild..."
productbuild \
  --distribution "$DIST_XML" \
  --resources "$RESOURCES_DIR" \
  --package-path "$BUILD_DIR" \
  "$FINAL_PKG"

echo "==> PKG created: $FINAL_PKG"
ls -lh "$FINAL_PKG"
