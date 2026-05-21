import markdown
import pdfkit

# Read MD
with open('bao-cao-thong-ke-thu-thap-du-lieu.md', 'r', encoding='utf-8') as f:
    md_content = f.read()

# Convert to HTML
html_content = markdown.markdown(md_content)

# Add CSS
html_full = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Báo Cáo Thống Kê Thu Thập Dữ Liệu</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1, h2, h3 { color: #333; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
''' + html_content + '''
</body>
</html>
'''

# Save HTML
with open('bao-cao-thong-ke-thu-thap-du-lieu.html', 'w', encoding='utf-8') as f:
    f.write(html_full)

# Convert to PDF (requires wkhtmltopdf installed)
pdfkit.from_file('bao-cao-thong-ke-thu-thap-du-lieu.html', 'bao-cao-thong-ke-thu-thap-du-lieu.pdf')

print('Conversion completed!')