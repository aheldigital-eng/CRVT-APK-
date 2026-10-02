from pathlib import Path
import re

p = Path('crvt/app/src/main/java/fr/crvt/app/MainActivity.java')
if p.exists():
    s = p.read_text()
    s = s.replace('import android.app.Activity;\n', 'import android.app.Activity;\nimport android.content.ActivityNotFoundException;\nimport android.content.Intent;\nimport android.net.Uri;\n')
    s = s.replace('import android.webkit.WebChromeClient;\n', 'import android.webkit.WebChromeClient;\nimport android.webkit.ValueCallback;\n')
    if 'FILE_CHOOSER_REQUEST' not in s:
        s = s.replace('    private static final int CAMERA_REQUEST = 1001;\n', '    private static final int CAMERA_REQUEST = 1001;\n    private static final int FILE_CHOOSER_REQUEST = 1002;\n    private ValueCallback<Uri[]> filePathCallback;\n')
    old = '        webView.setWebChromeClient(new WebChromeClient());'
    new = """        webView.setWebChromeClient(new WebChromeClient() {
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
        });"""
    if old in s:
        s = s.replace(old, new)
    marker = '    @Override\n    public void onBackPressed() {'
    result = """    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER_REQUEST) {
            if (filePathCallback == null) return;
            Uri[] results = null;
            if (resultCode == RESULT_OK && data != null) {
                if (data.getData() != null) results = new Uri[]{data.getData()};
                else if (data.getClipData() != null) {
                    int count = data.getClipData().getItemCount();
                    results = new Uri[count];
                    for (int i = 0; i < count; i++) results[i] = data.getClipData().getItemAt(i).getUri();
                }
            }
            filePathCallback.onReceiveValue(results);
            filePathCallback = null;
        }
    }

"""
    if marker in s and 'protected void onActivityResult(int requestCode' not in s:
        s = s.replace(marker, result + marker)
    p.write_text(s)

for path in Path('crvt').rglob('index.html'):
    s = path.read_text()
    css = r'''<style id="crvt-mobile-fixes">
*{box-sizing:border-box}
@media(max-width:700px){
html,body{margin:0!important;min-height:100%!important}
body{padding-top:32px!important;padding-bottom:max(8px,env(safe-area-inset-bottom))!important}
header,nav,.header,.topbar,.app-header,.appbar,.navbar,.tabs,.steps,.stepbar,.top-nav,.navigation,.main-header{top:32px!important}
.modal{position:fixed!important;top:0!important;left:0!important;right:0!important;bottom:0!important;width:100vw!important;height:100dvh!important;min-height:100dvh!important;margin:0!important;padding:max(8px,env(safe-area-inset-top)) 6px max(8px,env(safe-area-inset-bottom)) 6px!important;overflow:hidden!important;z-index:2147483000!important;transform:none!important;isolation:isolate!important}
.modalbox{width:100%!important;height:100%!important;min-height:0!important;display:flex!important;flex-direction:column!important;gap:5px!important;overflow:hidden!important}
.tools{position:relative!important;z-index:20!important;flex:0 0 auto!important;width:100%!important;max-height:39dvh!important;min-height:0!important;overflow-y:auto!important;overflow-x:hidden!important;padding:5px!important;margin:0!important;overscroll-behavior:contain!important}
.tools .btn,.tools button{min-height:40px!important;max-height:52px!important;touch-action:manipulation!important}
.tools select{min-height:40px!important;touch-action:manipulation!important}
.canvaswrap{position:relative!important;z-index:10!important;flex:1 1 auto!important;min-height:0!important;width:100%!important;overflow:auto!important;margin:0!important;padding:0!important;-webkit-overflow-scrolling:touch!important}
.canvaswrap canvas,.canvaswrap img{max-width:100%!important}
}
</style>'''
    if 'crvt-mobile-fixes' in s:
        s = re.sub(r'<style id="crvt-mobile-fixes">.*?</style>', css, s, count=1, flags=re.S)
    elif '</head>' in s:
        s = s.replace('</head>', css + '</head>', 1)

    js = r'''<script id="crvt-report-fix">
(function(){
function getReport(){try{if(typeof window.reportHtml==='function'){var h=window.reportHtml();if(typeof h==='string'&&h.indexOf('<')>=0)return h;}}catch(e){}return null;}
function printReport(){
  var html=getReport();
  if(!html){try{window.print();}catch(e){}return;}
  try{
    var old=document.documentElement.innerHTML;
    document.open();
    document.write(html);
    document.close();
    setTimeout(function(){try{window.focus();window.print();}catch(e){}},800);
  }catch(e){try{window.print();}catch(x){}}
}
function install(){
  var old=document.getElementById('crvtPdfFallback');if(old)old.remove();
  document.addEventListener('click',function(e){var el=e.target&&e.target.closest?e.target.closest('button,a,[role="button"]'):null;if(!el)return;var t=(el.innerText||el.textContent||'').replace(/\s+/g,' ').trim().toLowerCase();if(t.indexOf('pdf')>=0&&t.indexOf('imprim')>=0){e.preventDefault();e.stopImmediatePropagation();printReport();}},true);
  if(!document.querySelector('button[data-crvt-pdf],#crvtPdfFallback')){var b=document.createElement('button');b.id='crvtPdfFallback';b.type='button';b.dataset.crvtPdf='1';b.textContent='📄 PDF / Imprimer';b.style.cssText='position:fixed;right:12px;bottom:max(12px,env(safe-area-inset-bottom));z-index:2147482000;background:#0b6e9e;color:#fff;border:0;border-radius:12px;padding:13px 16px;font-weight:700;box-shadow:0 3px 12px #0005;touch-action:manipulation';b.addEventListener('click',printReport);document.body.appendChild(b);}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
</script>'''
    if 'crvt-report-fix' in s:
        s = re.sub(r'<script id="crvt-report-fix">.*?</script>', js, s, count=1, flags=re.S)
    elif '</body>' in s:
        s = s.replace('</body>', js + '</body>', 1)
    path.write_text(s)
    print('CRVT fixes:', path)
