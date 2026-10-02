from pathlib import Path
import re

# CRVT build patch: keep the WebView inside the Android system bars, make the
# annotation controls fully reachable, and use the native Android print
# pipeline for a real A4 PDF / printer dialog.

MAIN_ACTIVITY = r'''package fr.crvt.app;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.print.PrintAttributes;
import android.print.PrintManager;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {
    private WebView webView;
    private WebView printWebView;
    private static final int CAMERA_REQUEST = 1001;
    private static final int FILE_CHOOSER_REQUEST = 1002;
    private ValueCallback<Uri[]> filePathCallback;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getWindow().setStatusBarColor(Color.WHITE);
        getWindow().setNavigationBarColor(Color.WHITE);
        if (android.os.Build.VERSION.SDK_INT >= 23) {
            getWindow().getDecorView().setSystemUiVisibility(
                android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR |
                android.view.View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
            );
        }

        webView = new WebView(this);
        webView.setBackgroundColor(Color.WHITE);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setDatabaseEnabled(true);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setMediaPlaybackRequiresUserGesture(false);

        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (filePathCallback != null) filePathCallback.onReceiveValue(null);
                filePathCallback = callback;
                try {
                    Intent intent = params.createIntent();
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                    return true;
                } catch (ActivityNotFoundException e) {
                    filePathCallback = null;
                    return false;
                }
            }
        });

        webView.addJavascriptInterface(new CrvtNativeBridge(), "CRVTNative");

        // Android 15+/target 35 can draw edge-to-edge. Publish the real system
        // bar heights to CSS so fixed navigation/modals never sit underneath them.
        if (android.os.Build.VERSION.SDK_INT >= 23) {
            webView.setOnApplyWindowInsetsListener((v, insets) -> {
                int top = insets.getSystemWindowInsetTop();
                int bottom = insets.getSystemWindowInsetBottom();
                final int t = top;
                final int b = bottom;
                v.post(() -> v.evaluateJavascript(
                    "document.documentElement.style.setProperty('--crvt-statusbar','" + t + "px');" +
                    "document.documentElement.style.setProperty('--crvt-navbar','" + b + "px');" +
                    "if(window.crvtApplySystemInsets)window.crvtApplySystemInsets(" + t + "," + b + ");",
                    null
                ));
                return insets;
            });
            webView.requestApplyInsets();
        }

        if (android.os.Build.VERSION.SDK_INT >= 23 &&
            checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.CAMERA}, CAMERA_REQUEST);
        }

        webView.loadUrl("file:///android_asset/index.html");
    }

    private class CrvtNativeBridge {
        @JavascriptInterface
        public void printReport(String html) {
            if (html == null || html.length() < 100) return;
            runOnUiThread(() -> {
                try {
                    if (printWebView != null) {
                        printWebView.stopLoading();
                        printWebView.destroy();
                    }
                    printWebView = new WebView(MainActivity.this);
                    WebSettings ps = printWebView.getSettings();
                    ps.setJavaScriptEnabled(true);
                    ps.setDomStorageEnabled(true);
                    printWebView.setWebViewClient(new WebViewClient() {
                        @Override
                        public void onPageFinished(WebView view, String url) {
                            view.postDelayed(() -> startNativePrint(view), 500);
                        }
                    });
                    printWebView.loadDataWithBaseURL("file:///android_asset/", html, "text/html", "UTF-8", null);
                } catch (Exception ignored) {
                }
            });
        }

        private void startNativePrint(WebView view) {
            try {
                PrintManager printManager = (PrintManager) getSystemService(PRINT_SERVICE);
                PrintAttributes attrs = new PrintAttributes.Builder()
                    .setMediaSize(PrintAttributes.MediaSize.ISO_A4)
                    .setColorMode(PrintAttributes.COLOR_MODE_COLOR)
                    .setMinMargins(PrintAttributes.Margins.NO_MARGINS)
                    .build();
                printManager.print("CRVT - Compte rendu de visite technique",
                    view.createPrintDocumentAdapter("CRVT"), attrs);
            } catch (Exception ignored) {
            }
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER_REQUEST) {
            if (filePathCallback == null) return;
            Uri[] results = null;
            if (resultCode == RESULT_OK && data != null) {
                if (data.getData() != null) {
                    results = new Uri[]{data.getData()};
                } else if (data.getClipData() != null) {
                    int count = data.getClipData().getItemCount();
                    results = new Uri[count];
                    for (int i = 0; i < count; i++) {
                        results[i] = data.getClipData().getItemAt(i).getUri();
                    }
                }
            }
            filePathCallback.onReceiveValue(results);
            filePathCallback = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (webView == null) {
            super.onBackPressed();
            return;
        }
        webView.evaluateJavascript(
            "(window.crvtHandleBack ? window.crvtHandleBack() : false)",
            value -> {
                if ("true".equals(value)) return;
                if (webView.canGoBack()) webView.goBack();
                else MainActivity.super.onBackPressed();
            }
        );
    }
}
'''

MOBILE_CSS = r'''<style id="crvt-mobile-fixes">
*{box-sizing:border-box}
:root{--crvt-statusbar:0px;--crvt-navbar:0px}
html,body{margin:0!important;min-height:100%!important}
body{padding-top:calc(var(--crvt-statusbar,0px) + 54px)!important;padding-bottom:var(--crvt-navbar,0px)!important;overflow-x:hidden!important}
#quickNav{top:var(--crvt-statusbar,0px)!important;z-index:250!important}
@media(max-width:700px){
  #quickNav{top:var(--crvt-statusbar,0px)!important}
  .modal,.overlay,[role="dialog"]{position:fixed!important;top:var(--crvt-statusbar,0px)!important;left:0!important;right:0!important;bottom:var(--crvt-navbar,0px)!important;width:100vw!important;height:calc(100dvh - var(--crvt-statusbar,0px) - var(--crvt-navbar,0px))!important;min-height:0!important;margin:0!important;padding:8px 6px 8px!important;overflow:hidden!important;z-index:2147483000!important;transform:none!important;isolation:isolate!important}
  .modalbox{width:100%!important;height:100%!important;min-height:0!important;display:flex!important;flex-direction:column!important;gap:5px!important;overflow:hidden!important}
  .tools{position:relative!important;z-index:20!important;flex:0 0 auto!important;width:100%!important;max-height:47dvh!important;min-height:0!important;overflow-y:auto!important;overflow-x:hidden!important;padding:5px!important;margin:0!important;overscroll-behavior:contain!important;-webkit-overflow-scrolling:touch!important}
  .tools .btn,.tools button{min-height:40px!important;max-height:52px!important;touch-action:manipulation!important}
  .tools select{min-height:40px!important;touch-action:manipulation!important}
  .annotationActions{position:sticky!important;bottom:0!important;z-index:60!important;display:flex!important;gap:6px!important;padding:6px!important;margin:6px -1px -1px!important;background:rgba(255,255,255,.98)!important;border-top:1px solid #cbd5e1!important;box-shadow:0 -3px 10px rgba(0,0,0,.10)!important}
  .annotationActions>*{flex:1 1 0!important;min-width:0!important}
  .canvaswrap{position:relative!important;z-index:10!important;flex:1 1 auto!important;min-height:0!important;width:100%!important;overflow:auto!important;margin:0!important;padding:0!important;-webkit-overflow-scrolling:touch!important}
  .canvaswrap canvas,.canvaswrap img{max-width:100%!important}
  .photoViewer{top:var(--crvt-statusbar,0px)!important;bottom:var(--crvt-navbar,0px)!important;height:calc(100dvh - var(--crvt-statusbar,0px) - var(--crvt-navbar,0px))!important;inset-inline:0!important;padding:18px!important}
  .photoViewerClose{top:12px!important;right:14px!important;z-index:20!important}
  .photoViewerRotate{top:68px!important;right:14px!important;z-index:20!important;width:48px!important;height:48px!important}
  #photoViewerImg{max-width:92vw!important;max-height:calc(100dvh - var(--crvt-statusbar,0px) - var(--crvt-navbar,0px) - 150px)!important}
}
#crvtReportOverlay{font-family:Arial,sans-serif!important}
#crvtReportOverlay *{box-sizing:border-box!important}
#crvtReportOverlay{top:var(--crvt-statusbar,0px)!important;bottom:var(--crvt-navbar,0px)!important;height:calc(100dvh - var(--crvt-statusbar,0px) - var(--crvt-navbar,0px))!important}
</style>'''

REPORT_JS = r'''<script id="crvt-report-fix">
(function(){
'use strict';
var overlay=null, reportFrame=null, previousScroll=0;
function buildReportHtml(){
  try{
    if(typeof window.report==='function'){
      var h=window.report(false);
      if(typeof h==='string' && h.length>100) return h;
    }
  }catch(e){console.warn('CRVT report(false)',e);}
  return null;
}
function closeReport(){
  if(!overlay) return false;
  overlay.remove();overlay=null;reportFrame=null;document.body.style.overflow='';window.scrollTo(0,previousScroll);return true;
}
function printReport(){
  var html=buildReportHtml();
  if(!html){alert('Impossible de générer le rapport.');return false;}
  try{
    if(window.CRVTNative && typeof window.CRVTNative.printReport==='function'){
      window.CRVTNative.printReport(html);
      return true;
    }
  }catch(e){console.warn('CRVT native print',e);}
  try{
    if(!overlay) showReport(false);
    setTimeout(function(){
      if(reportFrame&&reportFrame.contentWindow){reportFrame.contentWindow.focus();reportFrame.contentWindow.print();}
      else window.print();
    },700);
    return true;
  }catch(e2){alert('Impression indisponible sur cet appareil.');return false;}
}
function showReport(autoPrint){
  var html=buildReportHtml();
  if(!html){alert('Impossible de générer le rapport.');return false;}
  closeReport();
  previousScroll=window.scrollY||0;
  overlay=document.createElement('div');
  overlay.id='crvtReportOverlay';
  overlay.style.cssText='position:fixed;left:0;right:0;top:var(--crvt-statusbar,0px);bottom:var(--crvt-navbar,0px);z-index:2147483646;background:#fff;display:flex;flex-direction:column;';
  var bar=document.createElement('div');
  bar.style.cssText='min-height:60px;flex:0 0 auto;display:flex;align-items:center;justify-content:space-between;gap:7px;padding:8px 9px;background:#08739f;color:#fff;font-weight:700;';
  var title=document.createElement('div');title.textContent='Compte rendu de visite technique';title.style.cssText='font-size:14px;flex:1;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;';
  var actions=document.createElement('div');actions.style.cssText='display:flex;gap:6px;flex:0 0 auto;';
  var back=document.createElement('button');back.type='button';back.textContent='← Retour';back.style.cssText='border:0;border-radius:9px;padding:10px 9px;background:#fff;color:#123;font-weight:700;';back.onclick=function(e){e.preventDefault();closeReport();};
  var pr=document.createElement('button');pr.type='button';pr.textContent='📄 PDF / Imprimer';pr.style.cssText='border:0;border-radius:9px;padding:10px 9px;background:#075577;color:#fff;font-weight:700;';pr.onclick=function(e){e.preventDefault();printReport();};
  actions.appendChild(back);actions.appendChild(pr);bar.appendChild(title);bar.appendChild(actions);
  reportFrame=document.createElement('iframe');
  reportFrame.id='crvtReportFrame';reportFrame.title='Rapport CRVT';reportFrame.style.cssText='border:0;display:block;flex:1 1 auto;width:100%;height:100%;background:#fff;';
  reportFrame.setAttribute('sandbox','allow-same-origin allow-modals allow-scripts');
  overlay.appendChild(bar);overlay.appendChild(reportFrame);document.body.appendChild(overlay);document.body.style.overflow='hidden';
  reportFrame.onload=function(){if(autoPrint)setTimeout(printReport,300);};
  try{reportFrame.srcdoc=html;}catch(e){var d=reportFrame.contentDocument;d.open();d.write(html);d.close();}
  return true;
}
function installReportButtons(){
  document.addEventListener('click',function(e){
    var el=e.target&&e.target.closest?e.target.closest('button,a,[role="button"]'):null;
    if(!el)return;
    var t=(el.innerText||el.textContent||'').replace(/\s+/g,' ').trim().toLowerCase();
    if(t.indexOf('pdf')>=0 || (t.indexOf('imprim')>=0 && t.length<90)){
      e.preventDefault();e.stopImmediatePropagation();showReport(false);return;
    }
    if((t==='retour'||t.indexOf('retour à')===0) && overlay){e.preventDefault();e.stopImmediatePropagation();closeReport();}
  },true);
}
function groupAnnotationActions(){
  document.querySelectorAll('.modal .tools').forEach(function(tools){
    if(tools.querySelector('.annotationActions'))return;
    var clear=tools.querySelector('#clear'), cancel=tools.querySelector('#cancel'), done=tools.querySelector('#done');
    if(!clear||!cancel||!done)return;
    var box=document.createElement('div');box.className='annotationActions';
    tools.appendChild(box);box.appendChild(clear);box.appendChild(cancel);box.appendChild(done);
  });
}
function applySystemInsets(top,bottom){
  document.documentElement.style.setProperty('--crvt-statusbar',(Number(top)||0)+'px');
  document.documentElement.style.setProperty('--crvt-navbar',(Number(bottom)||0)+'px');
  var nav=document.getElementById('quickNav');
  if(nav)nav.style.top=(Number(top)||0)+'px';
  var q=nav?nav.offsetHeight:0;
  document.body.style.paddingTop=((Number(top)||0)+q+8)+'px';
}
function install(){
  installReportButtons();
  groupAnnotationActions();
  applySystemInsets(parseInt(getComputedStyle(document.documentElement).getPropertyValue('--crvt-statusbar'))||0,parseInt(getComputedStyle(document.documentElement).getPropertyValue('--crvt-navbar'))||0);
  var obs=new MutationObserver(function(){groupAnnotationActions();});
  obs.observe(document.body,{childList:true,subtree:true});
}
window.crvtApplySystemInsets=applySystemInsets;
window.crvtShowReport=showReport;
window.crvtCloseReport=closeReport;
window.crvtPrintReport=printReport;
window.crvtHandleBack=function(){return closeReport();};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
</script>'''

for path in Path('crvt').rglob('index.html'):
    s = path.read_text()
    s = re.sub(r'<style id="crvt-mobile-fixes">.*?</style>', '', s, flags=re.S)
    s = re.sub(r'<script id="crvt-report-fix">.*?</script>', '', s, flags=re.S)
    if '</head>' in s:
        s = s.replace('</head>', MOBILE_CSS + '</head>', 1)
    if '</body>' in s:
        s = s.replace('</body>', REPORT_JS + '</body>', 1)
    path.write_text(s)

for p in Path('crvt').rglob('MainActivity.java'):
    p.write_text(MAIN_ACTIVITY)
    print('CRVT native Android patch:', p)

print('CRVT mobile/PDF fixes applied')
