package com.pagevault.app

import android.Manifest
import android.annotation.SuppressLint
import android.app.DownloadManager
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.util.Log
import android.view.View
import android.webkit.PermissionRequest
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.content.pm.PackageInfoCompat
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.pagevault.app.databinding.ActivityMainBinding
import java.io.File
import kotlin.concurrent.thread

/**
 * Hosts the PageVault web UI in a WebView backed by an on-device Flask server.
 *
 * On launch it starts embedded CPython (Chaquopy), extracts the bundled web
 * assets, asks the Python entry point to serve the app on a loopback port, then
 * points the WebView at it. Everything else (the catalogue, scanner, reader,
 * stats) is the existing web application running locally.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private var serverPort = 0

    // Held while the OS camera-permission dialog is up, so the WebView's
    // getUserMedia request can be granted or denied once the user answers.
    private var pendingCameraRequest: PermissionRequest? = null

    // Held while the system file picker is open, for <input type="file"> uploads.
    private var fileChooserCallback: ValueCallback<Array<Uri>>? = null

    private val cameraPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            pendingCameraRequest?.let { request ->
                if (granted) {
                    request.grant(arrayOf(PermissionRequest.RESOURCE_VIDEO_CAPTURE))
                } else {
                    request.deny()
                    toast(getString(R.string.camera_denied))
                }
            }
            pendingCameraRequest = null
        }

    private val fileChooserLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            val callback = fileChooserCallback ?: return@registerForActivityResult
            callback.onReceiveValue(
                WebChromeClient.FileChooserParams.parseResult(result.resultCode, result.data)
            )
            fileChooserCallback = null
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        configureWebView()
        setupBackNavigation()
        binding.splashRetry.setOnClickListener { bootServer() }
        bootServer()
    }

    // ── Server boot ─────────────────────────────────────────────────────────────

    private fun bootServer() {
        showSplash(getString(R.string.splash_starting), retry = false)
        thread(name = "pagevault-boot") {
            try {
                if (!Python.isStarted()) {
                    Python.start(AndroidPlatform(this))
                }
                val dataDir = File(filesDir, "data").apply { mkdirs() }
                val webDir = extractWebAssets()

                val port = Python.getInstance()
                    .getModule("mobile_server")
                    .callAttr("start", dataDir.absolutePath, webDir.absolutePath)
                    .toInt()

                runOnUiThread {
                    serverPort = port
                    binding.webview.loadUrl("http://127.0.0.1:$port/")
                }
            } catch (t: Throwable) {
                Log.e(TAG, "Failed to start the local server", t)
                runOnUiThread { showSplash(getString(R.string.splash_failed), retry = true) }
            }
        }
    }

    /**
     * Copy `assets/web` (templates + static) into `filesDir/web` so Flask can
     * serve them from a real filesystem path. A version marker keeps normal
     * launches fast; it includes the APK's lastUpdateTime so every (re)install —
     * including debug deploys from Android Studio, where versionCode never
     * changes — refreshes the extracted copy instead of serving stale assets.
     */
    private fun extractWebAssets(): File {
        val webDir = File(filesDir, "web")
        val marker = File(webDir, ".version")
        val pkg = packageManager.getPackageInfo(packageName, 0)
        val currentVersion = "${PackageInfoCompat.getLongVersionCode(pkg)}-${pkg.lastUpdateTime}"

        if (marker.exists() && marker.readText() == currentVersion) {
            return webDir
        }

        webDir.deleteRecursively()
        webDir.mkdirs()
        copyAssetDir("web", webDir)
        marker.writeText(currentVersion)
        return webDir
    }

    private fun copyAssetDir(assetPath: String, target: File) {
        val children = assets.list(assetPath) ?: emptyArray()
        if (children.isEmpty()) {
            // A leaf: copy the file itself.
            assets.open(assetPath).use { input ->
                target.outputStream().use { output -> input.copyTo(output) }
            }
            return
        }
        target.mkdirs()
        for (child in children) {
            copyAssetDir("$assetPath/$child", File(target, child))
        }
    }

    // ── WebView configuration ────────────────────────────────────────────────────

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView() {
        binding.webview.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            // The in-page ISBN scanner opens the camera without a tap gesture.
            mediaPlaybackRequiresUserGesture = false
            // Everything (EPUB reader, covers, assets) loads from the local
            // server over http://127.0.0.1 — the WebView never needs file://
            // access, so it stays disabled (defence in depth).
            allowFileAccess = false
            cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
            setSupportZoom(false)
        }

        binding.webview.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView,
                request: WebResourceRequest,
            ): Boolean {
                val url = request.url
                // Keep the app inside the local server; hand external links (e.g.
                // the GitHub link in the About panel) to the system browser.
                if (url.host == "127.0.0.1") return false
                return try {
                    startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, url))
                    true
                } catch (e: ActivityNotFoundException) {
                    false
                }
            }

            override fun onPageFinished(view: WebView, url: String) {
                if (url.startsWith("http://127.0.0.1")) hideSplash()
            }
        }

        binding.webview.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest) {
                runOnUiThread { grantCameraIfRequested(request) }
            }

            override fun onShowFileChooser(
                webView: WebView,
                callback: ValueCallback<Array<Uri>>,
                params: FileChooserParams,
            ): Boolean {
                fileChooserCallback?.onReceiveValue(null)
                fileChooserCallback = callback
                return try {
                    fileChooserLauncher.launch(params.createIntent())
                    true
                } catch (e: ActivityNotFoundException) {
                    fileChooserCallback = null
                    toast(getString(R.string.file_picker_unavailable))
                    false
                }
            }
        }

        // CSV export, backups and similar server downloads are saved to the app's
        // Downloads folder (no storage permission needed on any supported API).
        binding.webview.setDownloadListener { url, userAgent, contentDisposition, mimeType, _ ->
            saveDownload(url, userAgent, contentDisposition, mimeType)
        }
    }

    private fun grantCameraIfRequested(request: PermissionRequest) {
        val wantsCamera = request.resources.contains(PermissionRequest.RESOURCE_VIDEO_CAPTURE)
        if (!wantsCamera) {
            request.deny()
            return
        }
        if (hasCameraPermission()) {
            request.grant(arrayOf(PermissionRequest.RESOURCE_VIDEO_CAPTURE))
        } else {
            pendingCameraRequest = request
            cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    private fun hasCameraPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) ==
            PackageManager.PERMISSION_GRANTED

    private fun saveDownload(
        url: String,
        userAgent: String?,
        contentDisposition: String?,
        mimeType: String?,
    ) {
        if (!url.startsWith("http")) {
            // blob:/data: URLs are produced client-side and cannot be fetched by
            // DownloadManager. The export/backup endpoints are served over http,
            // so this path is only a defensive fallback.
            toast(getString(R.string.download_unsupported))
            return
        }
        try {
            val fileName = URLUtil.guessFileName(url, contentDisposition, mimeType)
            val request = DownloadManager.Request(Uri.parse(url)).apply {
                setMimeType(mimeType)
                userAgent?.let { addRequestHeader("User-Agent", it) }
                setDestinationInExternalFilesDir(
                    this@MainActivity, Environment.DIRECTORY_DOWNLOADS, fileName
                )
                setNotificationVisibility(
                    DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED
                )
                setTitle(fileName)
            }
            (getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager).enqueue(request)
            toast(getString(R.string.download_started, fileName))
        } catch (e: Exception) {
            Log.e(TAG, "Download failed", e)
            toast(getString(R.string.download_failed))
        }
    }

    // ── Navigation ────────────────────────────────────────────────────────────────

    private fun setupBackNavigation() {
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (binding.webview.canGoBack()) {
                    binding.webview.goBack()
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })
    }

    // ── Splash overlay ────────────────────────────────────────────────────────────

    private fun showSplash(status: String, retry: Boolean) {
        binding.splashOverlay.apply {
            alpha = 1f
            visibility = View.VISIBLE
        }
        binding.splashStatus.text = status
        binding.splashProgress.visibility = if (retry) View.GONE else View.VISIBLE
        binding.splashRetry.visibility = if (retry) View.VISIBLE else View.GONE
    }

    private fun hideSplash() {
        if (binding.splashOverlay.visibility != View.VISIBLE) return
        binding.splashOverlay.animate()
            .alpha(0f)
            .setDuration(SPLASH_FADE_MS)
            .withEndAction { binding.splashOverlay.visibility = View.GONE }
            .start()
    }

    private fun toast(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
    }

    override fun onDestroy() {
        // Detach the WebView cleanly to avoid leaking the Activity context.
        binding.webview.apply {
            stopLoading()
            webChromeClient = null
            destroy()
        }
        super.onDestroy()
    }

    companion object {
        private const val TAG = "PageVault"
        private const val SPLASH_FADE_MS = 320L
    }
}
