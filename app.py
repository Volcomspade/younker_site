from flask import Flask, render_template, request, send_file, redirect, url_for
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import pandas as pd
import io
import re
import unicodedata
import zipfile

def create_app():
    app = Flask(__name__)

    def clean_filename(name):
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
        name = re.sub(r'[^\w\-\s\.]', '', name)
        name = name.replace(' ', '_')
        return name[:100]

    def extract_checklist_titles(pages_text):
        titles = []
        for i, text in enumerate(pages_text):
            if all(field in text for field in ["ID", "Name", "Description", "Company", "Checklist Status"]):
                match = re.search(
                    r"Name\s*[:\-]?\s*(.*?)\n(?=(ID|Description|Author|Created On|Tags|Custom Properties|Company|Priority|Status|Location|Equipment Name|Equipment Barcode))",
                    text, re.IGNORECASE | re.DOTALL
                )
                if match:
                    raw_title = match.group(1).strip()
                    raw_title = re.sub(
                        r"\s*(ID|Description|Author|Created On|Tags|Custom Properties|Company|Priority|Status|Location|Equipment Name|Equipment Barcode)\s*:?.*",
                        "", raw_title, flags=re.IGNORECASE)
                    titles.append((i, raw_title))
        return titles

    def overlay_white_footer(page):
        packet = io.BytesIO()
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        can = canvas.Canvas(packet, pagesize=(width, height))
        can.setFillColorRGB(1, 1, 1)
        can.rect(0, 0, width, 90, fill=True, stroke=False)
        can.save()
        packet.seek(0)
        overlay_pdf = PdfReader(packet)
        overlay_page = overlay_pdf.pages[0]
        page.merge_page(overlay_page)
        return page

    @app.route('/')
    def home():
        return render_template('home.html')

    @app.route('/checklist-splitter', methods=['GET', 'POST'])
    def checklist_splitter():
        if request.method == 'POST':
            file = request.files.get('pdf')
            if not file:
                return redirect(url_for('checklist_splitter'))

            file_bytes = file.read()
            pdf_reader = PdfReader(io.BytesIO(file_bytes))
            pages_text = [page.extract_text() or "" for page in pdf_reader.pages]
            checklist_titles = extract_checklist_titles(pages_text)

            if not checklist_titles:
                return render_template('index.html', summary=None, error="No checklists found.")

            start_indices = [idx for idx, _ in checklist_titles]
            end_indices = start_indices[1:] + [len(pages_text)]
            checklist_groups = [
                {"title": clean_filename(title), "start": start, "end": end}
                for (start, title), end in zip(checklist_titles, end_indices)
            ]

            summary_data = []
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zipf:
                for group in checklist_groups:
                    writer = PdfWriter()
                    for p in range(group["start"], group["end"]):
                        cleaned_page = overlay_white_footer(pdf_reader.pages[p])
                        writer.add_page(cleaned_page)
                    pdf_output = io.BytesIO()
                    writer.write(pdf_output)
                    filename = f"{group['title']}.pdf"
                    zipf.writestr(filename, pdf_output.getvalue())
                    summary_data.append({"Checklist Name": group['title'], "Start Page": group['start']+1, "End Page": group['end']})

            zip_buffer.seek(0)
            return send_file(zip_buffer, download_name="Checklist_Split.zip", as_attachment=True)

        return render_template('index.html', summary=None, error=None)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)