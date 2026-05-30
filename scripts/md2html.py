"""Simple md->html converter for project docs."""
import re, sys

def convert(text):
    # code blocks
    text = re.sub(r'```(\w*)\n(.*?)```', r'<pre style="background:#2d2d2d;padding:12px;border-radius:6px;overflow-x:auto;font-size:.72rem"><code>\2</code></pre>', text, flags=re.DOTALL)
    # inline code
    text = re.sub(r'`([^`]+)`', r'<code style="background:#3c3c3c;padding:1px 5px;border-radius:3px;font-size:.75rem">\1</code>', text)
    # bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # h3, h2, h1
    text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
    # tables
    lines = text.split('\n')
    result = []
    in_table = False
    for line in lines:
        if '|' in line and line.strip().startswith('|'):
            if not in_table:
                result.append('<table style="width:100%;border-collapse:collapse;font-size:.72rem">')
                in_table = True
            if '---' in line and '|' in line:
                continue
            cells = line.split('|')[1:-1]
            is_header = in_table and len(result) == 1
            tag = 'th' if is_header else 'td'
            result.append('<tr>' + ''.join(
                f'<{tag} style="border:1px solid #333;padding:4px 8px">{c.strip()}</{tag}>'
                for c in cells
            ) + '</tr>')
        else:
            if in_table:
                result.append('</table>')
                in_table = False
            result.append(line)
    if in_table:
        result.append('</table>')
    text = '\n'.join(result)
    # hr
    text = re.sub(r'^---$', r'<hr style="border-color:#333;margin:16px 0">', text, flags=re.MULTILINE)
    # paragraphs
    text = re.sub(r'\n\n+', '\n<p style="margin:8px 0">', text)
    return text

def main(input_path, output_path):
    with open(input_path) as f:
        md = f.read()
    body = convert(md)
    html = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sisyphus Roadmap v2</title>
<style>
:root{{--bg:#1e1e1e;--fg:#d4d4d4;--dim:#808080;--accent:#569cd6;--border:#333;--card:#252526}}
*{{margin:0;padding:0}}body{{background:var(--bg);color:var(--fg);font-family:-apple-system,sans-serif;padding:20px;max-width:800px;margin:0 auto;font-size:.82rem;line-height:1.6}}
h1{{font-size:1.3rem;color:var(--accent);margin:20px 0 10px;border-bottom:1px solid var(--border);padding-bottom:6px}}
h2{{font-size:1.05rem;color:var(--accent);margin:18px 0 8px}}
h3{{font-size:.9rem;color:#dcdcaa;margin:14px 0 6px}}
b{{color:#dcdcaa}}code{{color:#ce9178}}
table{{margin:8px 0}}th{{background:#252526;color:var(--accent);text-align:left}}td{{background:#1e1e1e}}
p{{margin:6px 0}}ul{{margin:4px 0 4px 20px}}li{{margin:3px 0}}
blockquote{{border-left:2px solid var(--accent);padding-left:12px;margin:8px 0;color:var(--dim);font-style:italic}}
</style></head><body>
{body}
</body></html>"""
    with open(output_path, 'w') as f:
        f.write(html)
    print(f"OK {len(html)} bytes -> {output_path}")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
