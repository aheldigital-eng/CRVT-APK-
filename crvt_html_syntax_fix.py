from pathlib import Path

# The report template contains a literal </script> inside a JavaScript
# template string. HTML parsers terminate the surrounding script there,
# leaving the following JavaScript visible as raw text. Escape the slash in
# the source so the JavaScript string still produces </script> at runtime.
for path in Path('crvt').rglob('index.html'):
    s = path.read_text()
    bad = '</script></body></html>'
    fixed = '<\\/script></body></html>'
    if bad in s:
        s = s.replace(bad, fixed)
        path.write_text(s)
        print('CRVT HTML script-boundary fix:', path)
