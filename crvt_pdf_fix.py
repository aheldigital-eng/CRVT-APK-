from pathlib import Path
import re

# Final PDF fix:
# The report is displayed inside a srcdoc iframe. The previous fix tried to
# rebuild the report by calling report() a second time, which is exactly what
# was failing on the device. Instead, keep the already displayed report and
# send its actual DOM HTML directly to the native Android print bridge.

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
    s=path.read_text(encoding='utf-8')

    # Add a parent-side bridge that accepts the HTML of the report currently
    # visible in the iframe and sends it directly to Android PrintManager.
    marker="window.crvtPrintReport=printReport;"
    bridge_parent="""window.crvtPrintHtml=function(html){\n  try{\n    if(html && html.length>100 && window.CRVTNative && typeof window.CRVTNative.printReport==='function'){\n      window.CRVTNative.printReport(html);\n      return true;\n    }\n  }catch(e){console.warn('CRVT print html',e);}\n  return false;\n};\nwindow.crvtPrintReport=printReport;"""
    if marker in s and 'window.crvtPrintHtml=function(html)' not in s:
        s=s.replace(marker,bridge_parent,1)

    # Make the already-generated report carry its own PDF/return bridge. This
    # is the critical fix: the button lives inside the srcdoc iframe, so the
    # parent document's click handler cannot see it.
    needle="return captured.length>100?captured:null;"
    replacement="""if(captured.length>100){\n      var bridge=BRIDGE_PLACEHOLDER;\n      var at=captured.toLowerCase().lastIndexOf('</body>');\n      if(at>=0) captured=captured.slice(0,at)+bridge+captured.slice(at);\n      else captured+=bridge;\n      return captured;\n    }\n    return null;"""
    if needle in s:
        encoded=repr(BRIDGE)
        replacement=replacement.replace('BRIDGE_PLACEHOLDER',encoded)
        s=s.replace(needle,replacement,1)
    else:
        # If the previous PDF patch changed the return line, inject the bridge
        # immediately before the end of buildReportHtml as a safe fallback.
        if 'id="crvt-pdf-bridge"' not in s:
            pattern=r'(function buildReportHtml\(\)\{.*?)(\n\})'
            def add(m):
                return m.group(1)+"\n      var bridge="+repr(BRIDGE)+";\n      if(typeof captured==='string' && captured.length>100){var at=captured.toLowerCase().lastIndexOf('</body>');if(at>=0)captured=captured.slice(0,at)+bridge+captured.slice(at);else captured+=bridge;}"+m.group(2)
            s,n=re.subn(pattern,add,s,count=1,flags=re.S)
            if not n:
                raise SystemExit('CRVT PDF fix: buildReportHtml block not found')

    path.write_text(s,encoding='utf-8')
    print('CRVT final PDF iframe bridge applied:',path)
