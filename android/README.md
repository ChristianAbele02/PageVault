# PageVault for Android

A fully on-device Android build of PageVault. It runs the existing Flask app on a
loopback port inside the app process (embedded CPython via Chaquopy) and renders
the existing web UI in a `WebView`. The camera ISBN scanner, catalogue, reader,
stats, import/export and backups all run locally.

See [`../ANDROID_APP_PLAN.md`](../ANDROID_APP_PLAN.md) for the design rationale.

## How it fits together

```
MainActivity (Kotlin)
  ├─ starts embedded CPython (Chaquopy)
  ├─ extracts assets/web  →  filesDir/web   (templates + static)
  ├─ mobile_server.start(dataDir, webDir)   →  Flask on 127.0.0.1:<port>
  └─ WebView loads http://127.0.0.1:<port>/
```

- The Flask source lives at the repository root and is the single source of
  truth. `app/build.gradle` copies it (`syncPythonSource`) and the web assets
  (`syncWebAssets`) into the build at assembly time, so nothing is duplicated in
  version control.
- `mobile_server.py` (the only committed Python here) sets `PAGEVAULT_DATA_DIR`,
  `PAGEVAULT_RESOURCE_DIR` and `PAGEVAULT_HTTPS=0`, then serves the app with
  waitress.
- Camera access works because `http://127.0.0.1` is a secure context, so no TLS
  or certificate is involved. `cryptography` is intentionally not bundled.

## Prerequisites

- Android Studio (bundles the Android SDK and its own JDK 17). The project's
  wrapper is Gradle 8.13.
- Android SDK Platform 34 and the NDK (Android Studio offers to install the NDK
  on first sync; Chaquopy needs it).
- A physical device with USB debugging is best for testing the real camera.

## Build and run

Open the `android/` folder in Android Studio, let it sync, then Run. Or from a
terminal:

```bash
cd android
./gradlew assembleDebug          # gradlew.bat on Windows
# APK: app/build/outputs/apk/debug/app-debug.apk
```

Install a debug build directly on a connected device with `./gradlew installDebug`.

## Version baseline

Set in `build.gradle` / `app/build.gradle`, confirm or bump on first sync:

| Component | Version |
|---|---|
| Gradle | 8.13 |
| Android Gradle Plugin | 8.13.2 |
| Kotlin | 1.9.24 |
| Chaquopy | 17.0.0 |
| Python | 3.13 |
| compileSdk / targetSdk | 34 |
| minSdk | 26 (Android 8.0) |

Chaquopy's Gradle DSL is version-specific. If you change the Chaquopy version,
check the matching syntax at <https://chaquo.com/chaquopy/doc/current/android.html>
(the `chaquopy { }` block and its `sourceSets`).

## Phase 0 verification checklist

The first build is where the toolchain versions get aligned. Confirm, in order:

1. Gradle sync succeeds (adjust AGP/Chaquopy/Kotlin versions if it complains).
2. The app launches and the splash gives way to the PageVault library (this
   proves embedded Python served the page from the device).
3. Tapping the scan button opens the camera (grant the permission prompt) and a
   barcode is read.
4. Adding the scanned book fills in metadata (needs internet) and it persists
   across an app restart (proves on-device storage).

## Troubleshooting

- **Gradle sync fails on the Chaquopy block**: the DSL differs slightly between
  Chaquopy majors. Align the Chaquopy version and the `chaquopy { }` syntax per
  its docs.
- **NDK not found**: install it via Android Studio's SDK Manager, or set
  `ndkVersion` in `app/build.gradle`.
- **Camera does not open**: confirm the `CAMERA` permission was granted, and that
  the page origin is `http://127.0.0.1` (the scanner needs a secure context; the
  loopback origin qualifies).
- **Blank screen after the splash**: check Logcat (tag `PageVault`) for a Python
  traceback from `mobile_server.start`.
