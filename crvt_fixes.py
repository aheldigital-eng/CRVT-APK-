from pathlib import Path

# Android natif: photo/camera/gallery chooser
p = Path('crvt/app/src/main/java/fr/crvt/app/MainActivity.java')
if p.exists():
    s = p.read_text()
    s = s.replace('import android.app.Activity;\n', 'import android.app.Activity;\nimport android.content.ActivityNotFoundException;\nimport android.content.Intent;\nimport android.net.Uri;\n')
    s = s.replace('import android.webkit.WebChromeClient;\n', 'import android.webkit.WebChromeClient;\nimport android.webkit.ValueCallback;\n')
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

    # Keep the annotation toolbar inside the modal layout and give the image/canvas the remaining space.
    css = """<style id="crvt-mobile-fixes">
@media(max-width:700px){
.modal{position:fixed!important;inset:0!important;padding:6px!important;overflow:hidden!important;z-index:1000!important}
.modalbox{height:100%!important;min-height:0!important;display:flex!important;flex-direction:column!important;gap:6px!important}
.tools{position:relative!important;z-index:5!important;flex:0 0 auto!important;max-height:27vh!important;min-height:0!important;overflow-y:auto!important;overflow-x:hidden!important;padding:6px!important;box-sizing:border-box!important}
.tools .btn{min-height:38px!important;max-height:44px!important}
.tools select{min-height:38px!important}
.canvaswrap{position:relative!important;z-index:1!important;flex:1 1 auto!important;min-height:0!important;overflow:auto!important;margin:0!important;padding:0!important}
}
</style>"""
    if 'crvt-mobile-fixes' not in s and '</head>' in s:
        s = s.replace('</head>', css + '</head>', 1)

    # Add an always-visible PDF/print fallback for Android WebView.
    js = """<script id="crvt-report-fix">
(function(){
  function printable(){
    try{
      var w=window.open('','_blank');
      if(!w){window.print();return;}
      var body=document.body.cloneNode(true);
      body.querySelectorAll('button,#crvtPdfFallback').forEach(function(x){x.remove();});
      w.document.open();
      w.document.write('<!doctype html><html><head><meta charset="utf-8"><title>Compte rendu de visite technique</title><style>@page{size:A4;margin:10mm}body{font-family:Arial,sans-serif}img{max-width:100%;height:auto}</style></head><body>'+body.innerHTML+'</body></html>');
      w.document.close();
      setTimeout(function(){try{w.focus();w.print();}catch(e){}},700);
    }catch(e){try{window.print();}catch(x){}}
  }
  function add(){
    if(document.getElementById('crvtPdfFallback')) return;
    var b=document.createElement('button');
    b.id='crvtPdfFallback';
    b.type='button';
    b.textContent='📄 PDF / Imprimer';
    b.style.cssText='position:fixed;right:12px;bottom:12px;z-index:5000;background:#0b6e9e;color:#fff;border:0;border-radius:12px;padding:12px 16px;font-weight:700;box-shadow:0 3px 12px #0005';
    b.addEventListener('click',printable);
    document.body.appendChild(b);
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',add); else add();
})();
</script>"""
    if 'crvt-report-fix' not in s and '</body>' in s:
        s = s.replace('</body>', js + '</body>', 1)

    path.write_text(s)
    print('Corrections CRVT:', path)
