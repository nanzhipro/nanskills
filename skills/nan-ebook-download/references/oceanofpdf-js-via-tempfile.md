# OceanofPDF: Reliable JavaScript Execution via Temp File

The nested-quote escaping in inline `osascript -e '...do JavaScript "..."'` is a recurring source of syntax errors. Use this temp-file pattern instead.

## Submit EPUB Download Form

```python
import subprocess

js_code = """
// Submit the EPUB form (second Fetching_Resource form)
var forms = document.querySelectorAll('form[action*="Fetching_Resource"]');
var epubForm = forms[1];
epubForm.submit();
"submitted";
"""

with open('/tmp/of.js', 'w') as f:
    f.write(js_code)

script = f'''
tell application "Safari"
    set js to read POSIX file "/tmp/of.js" as «class utf8»
    do JavaScript js in current tab of front window
end tell
'''

result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
print("STDOUT:", result.stdout)
```

## Extract Form Data (Debugging)

```python
import subprocess

js_code = """
var result = {forms: []};
document.querySelectorAll('form[action*="Fetching_Resource"]').forEach(function(f) {
  var inputs = [];
  f.querySelectorAll('input').forEach(function(inp) {
    inputs.push({name: inp.name, value: inp.value, type: inp.type});
  });
  result.forms.push({action: f.action, inputs: inputs});
});
JSON.stringify(result);
"""

with open('/tmp/of.js', 'w') as f:
    f.write(js_code)

script = f'''
tell application "Safari"
    set js to read POSIX file "/tmp/of.js" as «class utf8»
    do JavaScript js in current tab of front window
end tell
'''

result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
print(result.stdout)
```

## Pitfalls

- Always write JS to `/tmp/of.js` (or another temp path) rather than inline
- The `«class utf8»` coercion is critical — without it, AppleScript may mangle the JS
- OceanofPDF forms use `type="image"` inputs as submit buttons — `form.submit()` works regardless
- After submitting, wait 10–30 seconds then check `~/Downloads/_OceanofPDF.com_*` for the file
