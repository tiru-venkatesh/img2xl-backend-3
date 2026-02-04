import os
import uvicorn
import re
import shutil
import uuid
import pytesseract
from services.qa_llm import answer_question
from services.llm import call_llm
from services.excel_writer import json_to_excel
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pypdf import PdfReader
from pdf2image import convert_from_path

# 🔹 Services
from services.chunker import split_text
from services.store import store_user, store_document, store_chunk
from services.search import search_chunks

# ---------------- CONFIGURATION ----------------

IS_PRODUCTION = os.getenv("IS_PRODUCTION", "false").lower() == "true"

TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if not IS_PRODUCTION and os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

BASE_DIR = "uploads"
PDF_DIR = os.path.join(BASE_DIR, "pdfs")
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs("static", exist_ok=True)

# ---------------- APP SETUP ----------------
app = FastAPI(title="Img2XL Backend Prototype")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://img2xl.netlify.app",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- LOGIC ----------------

def analyze_text(text: str):
    return {
        "application_numbers": re.findall(r"\b\d{10,}\b", text),
        "ip_addresses": re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text),
        "dates": re.findall(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{2}-\d{2}-\d{4}\b", text),
        "times": re.findall(r"\b\d{2}:\d{2}(?::\d{2})?\b", text)
    }

def summarize_analysis(analysis: List[dict]):
    summary = {
        "pages_scanned": len(analysis),
        "text_layer_pages": [],
        "ocr_success_pages": [],
        "unique_application_like_numbers": set(),
        "unique_dates": set(),
        "unique_times": set(),
        "unique_ip_addresses": set()
    }

    for page in analysis:
        if page["text_layer_present"]:
            summary["text_layer_pages"].append(page["page"])
        if page["ocr_status"] == "success":
            summary["ocr_success_pages"].append(page["page"])

        d = page["details"]
        summary["unique_application_like_numbers"].update(d["application_numbers"])
        summary["unique_dates"].update(d["dates"])
        summary["unique_times"].update(d["times"])
        summary["unique_ip_addresses"].update(d["ip_addresses"])

    for k in summary:
        if isinstance(summary[k], set):
            summary[k] = list(summary[k])

    return summary

def generate_paragraph_summary(summary):
    return f"Document contains {summary['pages_scanned']} pages."

# ---------------- ROUTES ----------------
app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/", response_class=HTMLResponse)
async def home():
    return FileResponse("static/index.html")

# ---------------- UPLOAD API ----------------

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF allowed")

    doc_id = str(uuid.uuid4())
    pdf_path = os.path.join(PDF_DIR, f"{doc_id}.pdf")

    try:
        with open(pdf_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        reader = PdfReader(pdf_path)
        analysis = []

        # ---------- OCR LOOP ----------
        for i, page in enumerate(reader.pages):

            text_layer = page.extract_text() or ""
            ocr_text = ""
            ocr_status = "skipped"

            try:
                images = convert_from_path(pdf_path, first_page=i+1, last_page=i+1)
                ocr_text = pytesseract.image_to_string(images[0])
                ocr_status = "success"
            except:
                ocr_status = "failed"

            combined = (text_layer + "\n" + ocr_text).strip()

            analysis.append({
                "page": i + 1,
                "text_layer_present": bool(text_layer.strip()),
                "ocr_status": ocr_status,
                "combined_text": combined,
                "details": analyze_text(combined)
            })

        # ---------- SUMMARY ----------
        summary = summarize_analysis(analysis)

        # ---------- STORE IN SUPABASE ----------
        full_text = "\n".join([p["combined_text"] for p in analysis])

        user_id = store_user("demo@img2xl.com")
        doc_db_id = store_document(user_id, file.filename)

        chunks = split_text(full_text)

        for c in chunks:
            store_chunk(doc_db_id, c)

        best_chunks = search_chunks("extract table")

        excel_file = None

        try:
            with open("prompts/structure_prompt.txt") as f:
                base_prompt = f.read()

            context = "\n".join([c["chunk_text"] for c in best_chunks])
            structured_json = call_llm(base_prompt + context)
            excel_file = json_to_excel(structured_json)

        except Exception as e:
            print("Phase 7 skipped:", e)


        # ---------- RESPONSE ----------
        return {
            "document_id": doc_id,
            "filename": file.filename,
            "pages": len(reader.pages),
            "summary": summary,
            "excel_file": excel_file,
            "human_summary": generate_paragraph_summary(summary),
            "stored_in_database": True,
            "total_chunks": len(chunks),
            "sample_retrieved_chunk": best_chunks[0]["chunk_text"] if best_chunks else None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
from pydantic import BaseModel

class AskRequest(BaseModel):
    question: str


@app.post("/ask")
async def ask_question(payload: AskRequest):

    try:
        question = payload.question

        results = search_chunks(question)

        if not results:
            return {"answer": "No relevant data found in document."}

        context = "\n".join([r["chunk_text"] for r in results])

        answer = answer_question(context, question)

        return {
            "question": question,
            "answer": answer
        }

    except Exception as e:
        print("ASK ERROR:", str(e))
        return {
            "answer": "AI service temporarily unavailable. Please try again."
        }


# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)

