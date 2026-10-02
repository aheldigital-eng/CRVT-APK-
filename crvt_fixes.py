from pathlib import Path
import re

# ---------- Android WebView: photo/file chooser ----------
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

# ---------- HTML / mobile UI fixes ----------
for path in Path('crvt').rglob('index.html'):
    s = path.read_text()

    css = r'''<style id="crvt-mobile-fixes">
*{box-sizing:border-box}
html,body{margin:0!important;min-height:100%!important}
@media(max-width:700px){
body{padding-top:36px!important;padding-bottom:max(10px,env(safe-area-inset-bottom))!important;overflow-x:hidden!important}
header,nav,.header,.topbar,.app-header,.appbar,.navbar,.tabs,.steps,.stepbar,.top-nav,.navigation,.main-header{top:36px!important;z-index:100!important}
.modal,.overlay,[role="dialog"]{position:fixed!important;top:36px!important;left:0!important;right:0!important;bottom:0!important;width:100vw!important;height:calc(100dvh - 36px)!important;min-height:0!important;margin:0!important;padding:8px 6px max(10px,env(safe-area-inset-bottom)) 6px!important;overflow:hidden!important;z-index:2147483000!important;transform:none!important;isolation:isolate!important}
.modalbox{width:100%!important;height:100%!important;min-height:0!important;display:flex!important;flex-direction:column!important;gap:5px!important;overflow:hidden!important}
.tools{position:relative!important;z-index:20!important;flex:0 0 auto!important;width:100%!important;max-height:42dvh!important;min-height:0!important;overflow-y:auto!important;overflow-x:hidden!important;padding:5px!important;margin:0!important;overscroll-behavior:contain!important}
.tools .btn,.tools button{min-height:40px!important;max-height:52px!important;touch-action:manipulation!important}
.tools select{min-height:40px!important;touch-action:manipulation!important}
.canvaswrap{position:relative!important;z-index:10!important;flex:1 1 auto!important;min-height:0!important;width:100%!important;overflow:auto!important;margin:0!important;padding:0!important;-webkit-overflow-scrolling:touch!important}
.canvaswrap canvas,.canvaswrap img{max-width:100%!important}
}
#crvtReportOverlay{font-family:Arial,sans-serif!important}
#crvtReportOverlay *{box-sizing:border-box!important}
</style>'''
    if 'crvt-mobile-fixes' in s:
        s = re.sub(r'<style id="crvt-mobile-fixes">.*?</style>', css, s, count=1, flags=re.S)
    elif '</head>' in s:
        s = s.replace('</head>', css + '</head>', 1)

    # ---------- CRVT report viewer ----------
    # Never replace the application DOM with document.open()/document.write().
    # The report is displayed in an in-app overlay and can always be closed.
    # Printing is done from a dedicated hidden iframe first; if the WebView
    # blocks it, we fall back to window.print().
    js = r'''<script id="crvt-report-fix">
(function(){
'use strict';
var overlay=null, reportFrame=null, previousScroll=0;
function buildReportHtml(){
  try{
    if(typeof window.reportHtml==='function'){
      var h=window.reportHtml();
      if(typeof h==='string' && h.length>100) return h;
    }
  }catch(e){console.warn('CRVT reportHtml',e);}
  try{
    if(typeof reportHtml==='function'){
      var h2=reportHtml();
      if(typeof h2==='string' && h2.length>100) return h2;
    }
  }catch(e2){console.warn('CRVT reportHtml local',e2);}
  return null;
}
function closeReport(){
  if(overlay){overlay.remove();overlay=null;reportFrame=null;document.body.style.overflow='';window.scrollTo(0,previousScroll);}
}
function printReport(){
  var html=buildReportHtml();
  if(!html){ alert('Impossible de préparer le rapport.'); return; }
  if(!overlay) showReport(false);
  setTimeout(function(){
    try{
      var f=reportFrame;
      if(f && f.contentWindow){f.contentWindow.focus();f.contentWindow.print();return;}
    }catch(e){console.warn('iframe print',e);}
    try{window.print();}catch(e2){alert('Impression indisponible sur cet appareil.');}
  },700);
}
function showReport(autoPrint){
  var html=buildReportHtml();
  if(!html){alert('Impossible de générer le rapport.');return;}
  closeReport();
  previousScroll=window.scrollY||0;
  overlay=document.createElement('div');
  overlay.id='crvtReportOverlay';
  overlay.style.cssText='position:fixed;inset:0;z-index:2147483646;background:#fff;display:flex;flex-direction:column;padding-top:max(6px,env(safe-area-inset-top));padding-bottom:max(6px,env(safe-area-inset-bottom));';
  var bar=document.createElement('div');
  bar.style.cssText='height:58px;flex:0 0 58px;display:flex;align-items:center;justify-content:space-between;gap:7px;padding:7px 9px;background:#08739f;color:#fff;font-weight:700;';
  var title=document.createElement('div');title.textContent='Compte rendu de visite technique';title.style.cssText='font-size:14px;flex:1;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;';
  var actions=document.createElement('div');actions.style.cssText='display:flex;gap:6px;flex:0 0 auto;';
  var back=document.createElement('button');back.type='button';back.textContent='← Retour';back.style.cssText='border:0;border-radius:9px;padding:10px 9px;background:#fff;color:#123;font-weight:700;';back.onclick=closeReport;
  var pr=document.createElement('button');pr.type='button';pr.textContent='📄 PDF / Imprimer';pr.style.cssText='border:0;border-radius:9px;padding:10px 9px;background:#075577;color:#fff;font-weight:700;';pr.onclick=printReport;
  actions.appendChild(back);actions.appendChild(pr);bar.appendChild(title);bar.appendChild(actions);
  reportFrame=document.createElement('iframe');
  reportFrame.id='crvtReportFrame';reportFrame.title='Rapport CRVT';reportFrame.style.cssText='border:0;display:block;flex:1 1 auto;width:100%;height:100%;background:#fff;';
  reportFrame.setAttribute('sandbox','allow-same-origin allow-modals allow-scripts');
  overlay.appendChild(bar);overlay.appendChild(reportFrame);document.body.appendChild(overlay);document.body.style.overflow='hidden';
  reportFrame.onload=function(){if(autoPrint)setTimeout(printReport,300);};
  try{reportFrame.srcdoc=html;}catch(e){var d=reportFrame.contentDocument;d.open();d.write(html);d.close();}
}
function installReportButtons(){
  document.addEventListener('click',function(e){
    var el=e.target&&e.target.closest?e.target.closest('button,a,[role="button"]'):null;
    if(!el)return;
    var t=(el.innerText||el.textContent||'').replace(/\s+/g,' ').trim().toLowerCase();
    if(t.indexOf('pdf')>=0 || (t.indexOf('imprim')>=0 && t.length<80)){
      e.preventDefault();e.stopImmediatePropagation();showReport(false);return;
    }
    if(t==='retour' || t.indexOf('retour à')===0){
      if(overlay){e.preventDefault();e.stopImmediatePropagation();closeReport();}
    }
  },true);
}

// ---------- Photo viewer rotation ----------
function getCurrentPhoto(){
  try{
    var sec=window.currentPhotoViewerSec;
    var idx=window.currentPhotoViewerIndex;
    if(sec!=null && idx>=0 && window.audit && audit.photos && audit.photos[sec] && audit.photos[sec][idx]) return audit.photos[sec][idx];
  }catch(e){}
  return null;
}
function applyRotation(deg){
  var img=document.getElementById('photoViewerImg');
  if(!img)return false;
  var p=getCurrentPhoto();
  if(p){p.rotation=((Number(p.rotation)||0)+deg+360)%360;img.style.transform='rotate('+p.rotation+'deg)';}
  else{
    var cur=Number(img.getAttribute('data-crvt-rotation')||0);cur=(cur+deg+360)%360;img.setAttribute('data-crvt-rotation',cur);img.style.transform='rotate('+cur+'deg)';
  }
  try{if(typeof window.save==='function')window.save();}catch(e){}
  try{if(typeof window.render==='function')window.render();}catch(e){}
  return true;
}
function installPhotoRotation(){
  // Existing dedicated control(s).
  document.addEventListener('click',function(e){
    var el=e.target&&e.target.closest?e.target.closest('button,[role="button"],.btn'):null;
    if(!el)return;
    var id=(el.id||'').toLowerCase(), cls=(el.className||'').toString().toLowerCase();
    var title=(el.getAttribute('title')||el.getAttribute('aria-label')||'').toLowerCase();
    var text=(el.innerText||el.textContent||'').replace(/\s+/g,' ').trim().toLowerCase();
    var photoOpen=!!document.getElementById('photoViewer');
    if(!photoOpen)return;
    var rotate=(id.indexOf('rotate')>=0||cls.indexOf('rotate')>=0||title.indexOf('pivot')>=0||title.indexOf('rotation')>=0||text.indexOf('pivoter')>=0||text.indexOf('rotation')>=0);
    if(!rotate && (text.indexOf('15°')>=0 || text.indexOf('↻')>=0 || text.indexOf('↺')>=0)) rotate=true;
    if(rotate){
      e.preventDefault();e.stopImmediatePropagation();
      var sign=(text.indexOf('↺')>=0||text.indexOf('gauche')>=0||text.indexOf('−')>=0)?-1:1;
      applyRotation(15*sign);
    }
  },true);
}
function install(){installReportButtons();installPhotoRotation();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
window.crvtShowReport=showReport;window.crvtCloseReport=closeReport;window.crvtPrintReport=printReport;window.crvtRotatePhoto=applyRotation;
})();
</script>'''
    if 'crvt-report-fix' in s:
        s = re.sub(r'<script id="crvt-report-fix">.*?</script>', js, s, count=1, flags=re.S)
    elif '</body>' in s:
        s = s.replace('</body>', js + '</body>', 1)
    path.write_text(s)
    print('CRVT fixes:', path)
