# app.py
from flask import Flask, render_template, request, redirect, send_file
from PyPDF2 import PdfReader, PdfWriter
import os
import io
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def extract_checklist_ranges(pdf_reader):
    checklist_ranges = []
    for i, page in enumerate(pdf_reader.pages):
        text = page.extract_text()
        if not text:
            continue
        if 'Checklist:' in text:
            checklist_name = text.split('Checklist:')[1].split('\n')[0].strip()
            checklist_ranges.append({'Checklist Name': checklist_name, 'Start Page': i})

    for i in range(len(checklist_ranges)):
        if i + 1 < len(checklist_ranges):
            checklist_ranges[i]['End Page'] = checklist_ranges[i+1]['Start Page'] - 1
        else:
            checklist_ranges[i]['End Page'] = len(pdf_reader.pages) - 1
    return checklist_ranges

def split_pdf(input_path, checklist_ranges):
    pdf_reader = PdfReader(input_path)
    for checklist in checklist_ranges:
        pdf_writer = PdfWriter()
        for i in range(checklist['Start Page'], checklist['End Page'] + 1):
            pdf_writer.add_page(pdf_reader.pages[i])

        safe_name = checklist['Checklist Name'].replace(' ', '_').replace('/', '_')
        output_filename = f"{safe_name}.pdf"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        with open(output_path, 'wb') as f:
            pdf_writer.write(f)

def save_summary_pdf(checklist_ranges):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    textobject = c.beginText(50, 750)
    textobject.setFont("Helvetica", 12)
    textobject.textLine("Checklist Summary")
    textobject.moveCursor(0, 20)

    for item in checklist_ranges:
        line = f"{item['Checklist Name']}: Pages {item['Start Page'] + 1} - {item['End Page'] + 1}"
        textobject.textLine(line)
        textobject.moveCursor(0, 15)

    c.drawText(textobject)
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

@app.route('/', methods=['GET', 'POST'])
def index():
    summary = None
    error = None

    if request.method == 'POST':
        file = request.files.get('pdf')
        if not file:
            error = 'No file uploaded'
            return render_template('index.html', error=error)

        input_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(input_path)

        try:
            pdf_reader = PdfReader(input_path)
            checklist_ranges = extract_checklist_ranges(pdf_reader)
            split_pdf(input_path, checklist_ranges)
            summary = checklist_ranges
        except Exception as e:
            error = str(e)

    return render_template('index.html', summary=summary, error=error)

if __name__ == '__main__':
    app.run(debug=True)
