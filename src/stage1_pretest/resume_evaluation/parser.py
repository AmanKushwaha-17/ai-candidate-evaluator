"""
Downloads a resume from a Google Drive share link and extracts its text.
Stage 1 — pre-test. Three single-responsibility classes composed by one facade.
"""

from __future__ import annotations

import io
import re

import fitz  # PyMuPDF
import pdfplumber
import requests
from PyPDF2 import PdfReader

from src.stage1_pretest.resume_evaluation.models import ParsedResume, ParseStatus

_DRIVE_ID_PATTERN = re.compile(r"/d/([a-zA-Z0-9_-]+)")
_PDF_MAGIC = b"%PDF"
_CID_ARTIFACT_PATTERN = re.compile(r"\(cid:\d+\)")


class GDriveDownloader:
    """Fetches raw bytes from a Google Drive 'anyone with the link' share URL."""

    DOWNLOAD_URL = "https://drive.google.com/uc?export=download"

    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    def _extract_file_id(self, share_url: str) -> str | None:
        match = _DRIVE_ID_PATTERN.search(share_url)
        return match.group(1) if match else None

    def download(self, share_url: str) -> bytes:
        file_id = self._extract_file_id(share_url)
        if not file_id:
            raise ValueError(f"Could not extract a Drive file ID from: {share_url!r}")

        session = requests.Session()
        response = session.get(
            self.DOWNLOAD_URL, params={"id": file_id}, timeout=self.timeout, stream=True
        )
        response.raise_for_status()

        token = self._find_confirm_token(response)
        if token:
            response = session.get(
                self.DOWNLOAD_URL,
                params={"id": file_id, "confirm": token},
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()

        return response.content

    @staticmethod
    def _find_confirm_token(response: requests.Response) -> str | None:
        for key, value in response.cookies.items():
            if key.startswith("download_warning"):
                return value
        if response.headers.get("Content-Type", "").startswith("text/html"):
            match = re.search(r"confirm=([0-9A-Za-z_-]+)", response.text)
            if match:
                return match.group(1)
        return None


class ResumeTextExtractor:
    """PyMuPDF first (handles ligature/font-encoding issues best), then pdfplumber, then PyPDF2."""

    def is_pdf(self, file_bytes: bytes) -> bool:
        return file_bytes[:4] == _PDF_MAGIC

    def looks_garbled(self, text: str) -> bool:
        if not text:
            return True
        artifact_chars = sum(len(m.group()) for m in _CID_ARTIFACT_PATTERN.finditer(text))
        return artifact_chars > 0 and (artifact_chars / max(len(text), 1)) > 0.02

    def extract(self, file_bytes: bytes) -> tuple[str, bool]:
        attempts = [
            self._extract_with_pymupdf,
            self._extract_with_pdfplumber,
            self._extract_with_pypdf2,
        ]
        best_text = ""
        for attempt in attempts:
            try:
                text = attempt(file_bytes)
            except Exception:  # noqa: BLE001
                continue
            if not text:
                continue
            if not self.looks_garbled(text):
                return text, False
            if not best_text:
                best_text = text
        if best_text:
            return best_text, True
        raise ValueError("No extractor produced any text")

    def _extract_with_pymupdf(self, file_bytes: bytes) -> str:
        text_parts = []
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                text_parts.append(page.get_text())
        text = "\n".join(text_parts).strip()
        if not text:
            raise ValueError("PyMuPDF extracted no text")
        return text

    def _extract_with_pdfplumber(self, file_bytes: bytes) -> str:
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        text = "\n".join(text_parts).strip()
        if not text:
            raise ValueError("pdfplumber extracted no text")
        return text

    def _extract_with_pypdf2(self, file_bytes: bytes) -> str:
        reader = PdfReader(io.BytesIO(file_bytes))
        text_parts = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(text_parts).strip()
        if not text:
            raise ValueError("PyPDF2 extracted no text")
        return text


class ResumeParser:
    """Facade: resume_link -> ParsedResume. Never raises; failures are in the model."""

    def __init__(
        self,
        downloader: GDriveDownloader | None = None,
        extractor: ResumeTextExtractor | None = None,
    ):
        self._downloader = downloader or GDriveDownloader()
        self._extractor = extractor or ResumeTextExtractor()

    def parse(self, s_no: int | None, resume_link: str | None) -> ParsedResume:
        if not resume_link or not str(resume_link).strip():
            return ParsedResume(s_no=s_no, status=ParseStatus.NO_LINK)

        try:
            file_bytes = self._downloader.download(str(resume_link))
        except Exception as exc:  # noqa: BLE001
            return ParsedResume(s_no=s_no, status=ParseStatus.DOWNLOAD_FAILED, error=str(exc))

        if not self._extractor.is_pdf(file_bytes):
            return ParsedResume(
                s_no=s_no,
                status=ParseStatus.NOT_A_PDF,
                error="Downloaded content is not a PDF (link may require sign-in access).",
            )

        try:
            text, was_garbled = self._extractor.extract(file_bytes)
        except Exception as exc:  # noqa: BLE001
            return ParsedResume(s_no=s_no, status=ParseStatus.EXTRACTION_FAILED, error=str(exc))

        return ParsedResume(
            s_no=s_no,
            status=ParseStatus.OK,
            text=text,
            char_count=len(text),
            error="Text may be partially garbled (font encoding issue)" if was_garbled else None,
        )
