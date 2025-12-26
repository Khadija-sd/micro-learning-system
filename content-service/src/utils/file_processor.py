import PyPDF2
import io
from typing import Union
from fastapi import UploadFile, HTTPException
import os

class FileProcessor:
    @staticmethod
    async def process_upload(file: UploadFile) -> str:
        """Process uploaded file and extract text"""
        # Check file size (max 10MB)
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:  # 10MB
            raise HTTPException(status_code=400, detail="File too large (max 10MB)")
        
        # Check file type
        filename = file.filename.lower()
        
        if filename.endswith('.pdf'):
            return FileProcessor.extract_text_from_pdf(content)
        elif filename.endswith('.txt'):
            return content.decode('utf-8')
        else:
            raise HTTPException(status_code=400, detail="Only PDF and TXT files are supported")
    
    @staticmethod
    def extract_text_from_pdf(content: bytes) -> str:
        """Extract text from PDF bytes"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
            text = ""
            
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            
            return text.strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read PDF: {str(e)}")
    
    @staticmethod
    def save_upload(file: UploadFile, upload_dir: str = "uploads") -> str:
        """Save uploaded file to disk"""
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, file.filename)
        
        with open(file_path, "wb") as buffer:
            content = file.file.read()
            buffer.write(content)
        
        return file_path