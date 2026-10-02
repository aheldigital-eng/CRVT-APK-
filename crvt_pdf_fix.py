from pathlib import Path
import re

# CRVT PDF-only fix:
# Reuse the same report() path that already produces the working preview,
# capture its generated HTML with a fake window/document, then send it to the
# native Android print bridge.

NEW_BUILD = r'''function buildReportHtml(){
  try{
    if(typeof report!=='function') return null;
    var writes=[];
    var fakeDocument={
      title:'',
      open:function(){writes=[];},
      write:function(s){writes.push(String(s));},
      close:function(){},
      body:{},
      documentElement:{}
    };
    var fakeWindow={document:fakeDocument,focus:function(){},close:function(){}};
    var oldOpen=window.open;
    window.open=function(){return fakeWindow;};
    var returned=null;
    try{ returned=report(true); }
    finally{ window.open=oldOpen; }
    var captured=writes.join('');
    if(captured.indexOf('<!doctype')<0 && captured.indexOf('<html')<0){
      if(typeof returned==='string' && returned.length>100) captured=returned;
    }
    return captured.length>100?captured:null;
  }catch(e){
    console.error('CRVT PDF report build',e);
    return null;
  }
}'''

for path in Path('crvt').rglob('index.html'):
    s=path.read_text(encoding='utf-8')
    pattern=r'function buildReportHtml\(\)\{.*?\n\}\nfunction closeReport'
    replacement=NEW_BUILD+'\nfunction closeReport'
    fixed,n=re.subn(pattern,replacement,s,count=1,flags=re.S)
    if n:
        path.write_text(fixed,encoding='utf-8')
        print('CRVT PDF generation fix applied:',path)
    else:
        raise SystemExit('CRVT PDF fix: buildReportHtml block not found')
