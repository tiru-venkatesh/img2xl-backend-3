import os
import re
import shutil
import uuid
import pytesseract
import uvicorn

from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pypdf import PdfReader
from pdf2image import convert_from_path

# ---------------- SERVICES ----------------

from services.qa_llm import answer_question
from services.llm import call_llm
from services.excel_writer import json_to_excel
from services.chunker import split_text
from services.store import store_user, store_document, store_chunk
from services.search import search_chunks

# ---------------- FEATURE FLAGS ----------------

ENABLE_OCR = os.getenv("ENABLE_OCR", "true").lower() == "true"
IS_PRODUCTION = os.getenv("IS_PRODUCTION", "false").lower() == "true"

# ---------------- OCR CONFIG ----------------

if ENABLE_OCR and not IS_PRODUCTION:
    TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(TESSERACT_PATH):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# ---------------- STORAGE ----------------

BASE_DIR = "uploads"
PDF_DIR = os.path.join(BASE_DIR, "pdfs")

os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs("static", exist_ok=True)

# ---------------- APP ----------------

app = FastAPI(title="Img2XL Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------- HOME ----------------

@app.get("/", response_class=HTMLResponse)
async def home():
    return FileResponse("static/index.html")

# ---------------- HELPERS ----------------

def analyze_text(text: str):
    return {
        "application_numbers": re.findall(r"\b\d{10,}\b", text),
        "ip_addresses": re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text),
        "dates": re.findall(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{2}-\d{2}-\d{4}\b", text),
        "times": re.findall(r"\b\d{2}:\d{2}(?::\d{2})?\b", text)
    }

def summarize_analysis(analysis: List[dict]):
    return {
        "pages_scanned": len(analysis),
        "ocr_success_pages": [p["page"] for p in analysis if p["ocr_status"] == "success"]
    }

# ---------------- UPLOAD PDF ----------------

@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    use_ocr: bool = Form(True)
):

    if file.content_type != "application/pdf":
        raise HTTPException(400, "Only PDF files allowed")

    doc_id = str(uuid.uuid4())
    pdf_path = os.path.join(PDF_DIR, f"{doc_id}.pdf")

    try:
        # Save file
        with open(pdf_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        reader = PdfReader(pdf_path)
        analysis = []

        ocr_allowed = ENABLE_OCR and use_ocr

        # ---------- PAGE LOOP ----------
        for i, page in enumerate(reader.pages):

            text_layer = page.extract_text() or ""
            ocr_text = ""
            ocr_status = "skipped"

            if ocr_allowed:
                try:
                    images = convert_from_path(
                        pdf_path,
                        first_page=i + 1,
                        last_page=i + 1
                    )

                    ocr_text = pytesseract.image_to_string(
                        images[0],
                        lang="eng",
                        config="--oem 3 --psm 6"
                    )

                    ocr_status = "success"
                    print(f"\n--- PAGE {i+1} OCR SAMPLE ---\n", ocr_text[:300])

                except Exception as e:
                    print("OCR ERROR:", e)
                    ocr_status = "failed"

            combined_text = f"""
{text_layer}

----- OCR TEXT -----
{ocr_text}
""".strip()

            analysis.append({
                "page": i + 1,
                "ocr_status": ocr_status,
                "combined_text": combined_text,
                "details": analyze_text(combined_text)
            })

        # ---------- SUMMARY ----------
        summary = summarize_analysis(analysis)
        full_text = "\n".join(p["combined_text"] for p in analysis)

        # ---------- STORE ----------
        user_id = store_user("demo@img2xl.com")
        doc_db_id = store_document(user_id, file.filename)

        chunks = split_text(full_text)

        for c in chunks:
            store_chunk(doc_db_id, c)

        return {
            "document_id": doc_id,
            "filename": file.filename,
            "pages": len(reader.pages),
            "summary": summary,
            "ocr_enabled": ocr_allowed,
            "stored_in_database": True
        }

    except Exception as e:
        raise HTTPException(500, str(e))

# ---------------- ASK QUESTION ----------------

class AskRequest(BaseModel):
    question: str

@app.post("/ask")
async def ask_question(payload: AskRequest):

    try:
        results = search_chunks(payload.question)

        if not results:
            return {"answer": "No relevant data found in document."}

        context = "\n".join(r["chunk_text"] for r in results)

        answer = answer_question(context, payload.question)

        return {
    "answer": answer,
    "sources": results,
    "ocr_text": full_ocr_text
    "total_sources": len(results)
}


    except Exception as e:
        print("ASK ERROR:", e)
        return {"answer": "AI service temporarily unavailable."}

# ---------------- RUN SERVER ----------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
