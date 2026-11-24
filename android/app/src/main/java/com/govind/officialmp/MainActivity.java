package com.govind.officialmp;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

public class MainActivity extends Activity {
    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private static final int FILE_CHOOSER_REQUEST = 4102;
    private final Handler handler = new Handler();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (savedInstanceState == null) showWelcomeThenOpen();
        else createWebView(savedInstanceState);
    }

    private void showWelcomeThenOpen() {
        FrameLayout root = new FrameLayout(this);
        GradientDrawable bg = new GradientDrawable(
                GradientDrawable.Orientation.TL_BR,
                new int[]{Color.rgb(22, 16, 48), Color.rgb(93, 34, 104), Color.rgb(20, 24, 55)});
        root.setBackground(bg);

        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setGravity(Gravity.CENTER);
        content.setPadding(dp(28), dp(32), dp(28), dp(32));

        ImageView photo = new ImageView(this);
        photo.setImageResource(R.drawable.welcome_photo);
        photo.setScaleType(ImageView.ScaleType.CENTER_CROP);
        GradientDrawable photoBg = new GradientDrawable();
        photoBg.setColor(Color.WHITE);
        photoBg.setShape(GradientDrawable.OVAL);
        photo.setBackground(photoBg);
        photo.setClipToOutline(true);
        LinearLayout.LayoutParams photoParams = new LinearLayout.LayoutParams(dp(220), dp(220));
        photoParams.bottomMargin = dp(34);
        content.addView(photo, photoParams);

        TextView welcome = new TextView(this);
        welcome.setText("Welcome 🥰");
        welcome.setTextColor(Color.WHITE);
        welcome.setTextSize(34);
        welcome.setTypeface(Typeface.create("serif", Typeface.BOLD_ITALIC));
        welcome.setGravity(Gravity.CENTER);
        content.addView(welcome, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView jaan = new TextView(this);
        jaan.setText("मेरी जान");
        jaan.setTextColor(Color.rgb(255, 220, 245));
        jaan.setTextSize(36);
        jaan.setTypeface(Typeface.create("sans-serif", Typeface.BOLD));
        jaan.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams jaanParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        jaanParams.topMargin = dp(8);
        content.addView(jaan, jaanParams);

        TextView appName = new TextView(this);
        appName.setText("GOVIND OFFICIAL MP");
        appName.setTextColor(Color.rgb(225, 218, 245));
        appName.setTextSize(13);
        appName.setLetterSpacing(0.16f);
        appName.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams appParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        appParams.topMargin = dp(28);
        content.addView(appName, appParams);

        root.addView(content, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);
        handler.postDelayed(() -> createWebView(null), 2300);
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private void createWebView(Bundle savedInstanceState) {
        webView = new WebView(this);
        setContentView(webView);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setSupportMultipleWindows(false);
        CookieManager cookies = CookieManager.getInstance();
        cookies.setAcceptCookie(true);
        cookies.setAcceptThirdPartyCookies(webView, false);
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                Uri base = Uri.parse(BuildConfig.SERVER_URL);
                if (base.getHost() != null && base.getHost().equalsIgnoreCase(uri.getHost())
                        && "https".equalsIgnoreCase(uri.getScheme())) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); }
                catch (ActivityNotFoundException ignored) { }
                return true;
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                             FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                try {
                    startActivityForResult(params.createIntent(), FILE_CHOOSER_REQUEST);
                    return true;
                } catch (ActivityNotFoundException ex) {
                    fileCallback = null;
                    return false;
                }
            }
        });
        if (savedInstanceState == null) webView.loadUrl(BuildConfig.SERVER_URL);
        else webView.restoreState(savedInstanceState);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER_REQUEST && fileCallback != null) {
            fileCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
            fileCallback = null;
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        if (webView != null) webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        if (fileCallback != null) fileCallback.onReceiveValue(null);
        if (webView != null) webView.destroy();
        super.onDestroy();
    }
}
