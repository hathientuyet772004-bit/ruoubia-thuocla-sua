import logging
import json
import re
import os
import requests
import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Dict, Any, Optional
import google.generativeai as genai
from shared.config import settings
import tempfile

log = logging.getLogger("shared.ocr_service")

class OCRService:
    """
    [Scenario 14] OCR Extraction Service.
    Hybrid Strategy: EasyOCR (offline/local) + Gemini Vision (AI/fallback).
    Task: Extract Price, Volume, Brand, and Compliance Warnings from product images.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.use_mock = settings.USE_MOCK_MODE
        
        # Initialize EasyOCR (Lazy loading to save memory in ETL worker)
        self._reader = None
        
        # Initialize Gemini for Vision tasks
        if self.api_key and not self.use_mock:
            genai.configure(api_key=self.api_key)
            self.ai_model = genai.GenerativeModel("gemini-1.5-flash")
        else:
            self.ai_model = None

    @property
    def reader(self):
        if self._reader is None:
            try:
                import easyocr
                # Supports Vietnamese and English
                self._reader = easyocr.Reader(['vi', 'en'], gpu=False) 
                log.info("✅ EasyOCR Reader initialized.")
            except ImportError:
                log.error("❌ EasyOCR not installed. Run: pip install easyocr")
                self._reader = False
        return self._reader

    def download_image(self, url: str) -> Optional[str]:
        """Download image to a temporary file."""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                suffix = Path(url).suffix or ".jpg"
                if len(suffix) > 5: suffix = ".jpg"
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(response.content)
                    return tmp.name
        except Exception as e:
            log.error(f"Failed to download image {url}: {e}")
        return None

    def preprocess_image(self, img_path: str) -> str:
        """
        Enhance image for better OCR accuracy.
        Steps: Grayscale, Denoising, Thresholding.
        """
        try:
            img = cv2.imread(img_path)
            if img is None: return img_path
            
            # 1. Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 2. Rescaling (increase size if image is small)
            height, width = gray.shape
            if width < 1000:
                gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            
            # 3. Denoising
            denoised = cv2.fastNlMeansDenoising(gray, h=10)
            
            # 4. Adaptive Thresholding
            thresh = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            
            processed_path = img_path.replace(".", "_processed.")
            cv2.imwrite(processed_path, thresh)
            return processed_path
        except Exception as e:
            log.warning(f"Preprocessing failed: {e}. Using original image.")
            return img_path

    def extract_text_local(self, img_path: str) -> str:
        """Extract text using EasyOCR."""
        if not self.reader:
            return ""
        
        try:
            results = self.reader.readtext(img_path, detail=0)
            return " ".join(results)
        except Exception as e:
            log.error(f"EasyOCR extraction failed: {e}")
            return ""

    def extract_text_ai(self, img_path: str) -> Dict[str, Any]:
        """
        Deep extraction using Gemini Vision API.
        Best for: Hand-written price tags, complex layouts, compliance labels.
        """
        if not self.ai_model:
            return {"error": "AI model not available"}

        try:
            img = Image.open(img_path)
            prompt = """
            Analyze this product image (Liquor, Cigarette or Milk).
            Extract the following entities into JSON:
            1. detected_price: Numeric value only.
            2. detected_volume: Capacity (e.g., 750ml, 1L, 900g).
            3. detected_brand: Brand name shown on label.
            4. warnings: Any health or legal warnings (e.g., '18+', 'Dưới 18 tuổi').
            5. language: Predominant language on label.
            
            Output ONLY raw JSON.
            """
            response = self.ai_model.generate_content([prompt, img])
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            return json.loads(text)
        except Exception as e:
            log.error(f"Gemini Vision failed: {e}")
            return {}

    def parse_entities_from_text(self, text: str) -> Dict[str, Any]:
        """Regex-based entity extraction from raw text."""
        # Simple regex for prices (e.g., 250.000, 150k)
        price_match = re.search(r"(\d{1,3}(?:\.\d{3})*(?:\s?đ|\s?VND|k))", text, re.I)
        # Regex for volume (ml, L, g, kg)
        vol_match = re.search(r"(\d+(?:\.\d+)?\s?(?:ml|l|g|kg))", text, re.I)
        
        return {
            "detected_price_raw": price_match.group(0) if price_match else None,
            "detected_volume": vol_match.group(0) if vol_match else None,
            "warnings_found": "18+" in text or "dưới 18" in text.lower()
        }

    def process_product_image(self, image_url: str) -> Dict[str, Any]:
        """
        Main entry point for product image processing.
        Implements Hybrid Strategy with Cache logic.
        """
        log.info(f"🧐 Processing image OCR: {image_url}")
        
        img_path = self.download_image(image_url)
        if not img_path:
            return {"status": "error", "message": "download_failed"}

        try:
            # 1. Local OCR (Fast, no cost)
            raw_text_local = self.extract_text_local(img_path)
            entities_local = self.parse_entities_from_text(raw_text_local)
            
            # 2. Hybrid Decision: If local OCR is unsure or crucial info missing, call AI
            needs_ai = entities_local.get("detected_price_raw") is None or not raw_text_local
            
            ai_data = {}
            if needs_ai and self.ai_model:
                log.info("🤖 Local OCR insufficient. Falling back to Gemini Vision...")
                ai_data = self.extract_text_ai(img_path)

            # 3. Merge Results
            result = {
                "ocr_text_raw": raw_text_local,
                "detected_price": ai_data.get("detected_price") or entities_local.get("detected_price_raw"),
                "detected_volume": ai_data.get("detected_volume") or entities_local.get("detected_volume"),
                "detected_brand": ai_data.get("detected_brand"),
                "warnings": ai_data.get("warnings") or ("YES" if entities_local.get("warnings_found") else "NONE"),
                "engine": "Gemini-Vision" if ai_data else "EasyOCR",
                "confidence_score": 0.95 if ai_data else (0.7 if raw_text_local else 0.0)
            }
            
            return result

        finally:
            # Cleanup
            if img_path and os.path.exists(img_path):
                os.remove(img_path)
                processed = img_path.replace(".", "_processed.")
                if os.path.exists(processed): os.remove(processed)

if __name__ == "__main__":
    # Test script
    ocr = OCRService()
    test_url = "https://cdn.tgdd.vn/Products/Images/2282/236173/bhx/bia-heineken-silver-330ml-202303231454564883.jpg"
    print(json.dumps(ocr.process_product_image(test_url), indent=2, ensure_ascii=False))
