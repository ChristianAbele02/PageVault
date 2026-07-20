# Chaquopy and the WebView bridge rely on reflection; keep their entry points.
-keep class com.chaquo.python.** { *; }
-keep class com.pagevault.app.** { *; }

# Keep JavascriptInterface-annotated members (used by the file/save bridge).
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
