from pathlib import Path
import re
import json

# CRVT PDF bridge.
# IMPORTANT: BRIDGE is itself inserted into JavaScript which later writes a
# <script>...</script> block into the generated report. A literal </script>
# inside the OUTER index.html script terminates that outer script in WebView
# and causes the JavaScript source to appear as visible text. Escape the slash
# only while embedding the bridge as a JS string; when the string is evaluated
# at runtime, <\/script> becomes </script> again.

BRIDGE = r'''<script id="crvt-pdf-bridge">
(function(){
  function textOf(el){ return ((el && (el.innerText || el.textContent)) || '').replace(/\s+/g,' ').trim().toLowerCase(); }
  function parentCall(name,arg){
    try{
      if(window.parent && window.parent !== window && typeof window.parent[name] === 'function'){
        window.parent[name](arg);
        return true;
      }
    }catch(e){ console.warn('CRVT parent bridge',e); }
    return false;
  }
  document.addEventListener('click',function(e){
    var el=e.target && e.target.closest ? e.target.closest('button,a,[role="button"]') : null;
    if(!el) return;
    var t=textOf(el);
    if(t.indexOf('pdf')>=0 || (t.indexOf('imprim')>=0 && t.length<100)){
      e.preventDefault();
      e.stopImmediatePropagation();
      parentCall('crvtPrintHtml', document.documentElement.outerHTML);
      return;
    }
    if(t === 'retour' || t.indexOf('retour au')===0 || t.indexOf('retour à')===0 || t.indexOf('fermer')===0){
      e.preventDefault();
      e.stopImmediatePropagation();
      parentCall('crvtCloseReport');
    }
  },true);
})();
</script>'''

for path in Path('crvt').rglob('index.html'):
    s = path.read_text(encoding='utf-8')

    # Parent-side bridge: accept the HTML of the report currently visible in
    # the iframe and send it directly to Android PrintManager.
    marker = "window.crvtPrintReport=printReport;"
    bridge_parent = """window.crvtPrintHtml=function(html){
  try{
    if(html && html.length>100 && window.CRVTNative && typeof window.CRVTNative.printReport==='function'){
      window.CRVTNative.printReport(html);
      return true;
    }
  }catch(e){console.warn('CRVT print html',e);}
  return false;
};
window.crvtPrintReport=printReport;"""
    if marker in s and 'window.crvtPrintHtml=function(html)' not in s:
        s = s.replace(marker, bridge_parent, 1)

    # The report is generated as a string and loaded into an iframe srcdoc.
    # Install the bridge in that actual report so its PDF/Retour buttons work.
    needle = "return captured.length>100?captured:null;"
    if needle in s:
        # Escape </script> for the OUTER index.html script. Without this,
        # Android WebView closes the outer script early and displays the rest
        # of the JavaScript source as visible page text.
        bridge_js = json.dumps(BRIDGE).replace('</', '<\\/')
        replacement = """if(captured.length>100){
      var bridge=BRIDGE_PLACEHOLDER;
      var at=captured.toLowerCase().lastIndexOf('</body>');
      if(at>=0) captured=captured.slice(0,at)+bridge+captured.slice(at);
      else captured+=bridge;
      return captured;
    }
    return null;""".replace('BRIDGE_PLACEHOLDER', bridge_js)
        s = s.replace(needle, replacement, 1)
    elif 'id=\"crvt-pdf-bridge\"' not in s:
        pattern = r'(function buildReportHtml\(\)\{.*?)(\n\})'
        bridge_js = json.dumps(BRIDGE).replace('</', '<\\/')
        def add(m):
            inject = "\n      var bridge=" + bridge_js + ";\n      if(typeof captured==='string' && captured.length>100){var at=captured.toLowerCase().lastIndexOf('</body>');if(at>=0)captured=captured.slice(0,at)+bridge+captured.slice(at);else captured+=bridge;}"
            return m.group(1) + inject + m.group(2)
        s, n = re.subn(pattern, add, s, count=1, flags=re.S)
        if not n:
            raise SystemExit('CRVT PDF fix: buildReportHtml block not found')

    path.write_text(s, encoding='utf-8')
    print('CRVT PDF bridge safely embedded:', path)
