"""论文文本提取模块 — 支持 PDF 文件、PDF+图片目录"""
import base64
from pathlib import Path

import fitz  # PyMuPDF


def extract_from_pdf(pdf_path: Path) -> str:
    """从 PDF 文件提取全文文本"""
    doc = fitz.open(str(pdf_path))
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if text.strip():
            pages.append(f"--- Page {i + 1} ---\n{text.strip()}")
    doc.close()
    return "\n\n".join(pages)


def load_images_as_base64(image_dir: Path, max_pages: int = 25) -> list[dict]:
    """将论文页面图片编码为 base64，供 Vision 模型使用"""
    images = sorted(
        list(image_dir.glob("*.jpg")) + list(image_dir.glob("*.png")),
        key=lambda p: p.name,
    )
    images = images[:max_pages]

    result = []
    for img_path in images:
        with open(img_path, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode("utf-8")
        result.append({
            "path": str(img_path),
            "base64": b64,
            "mime": "image/jpeg" if img_path.suffix == ".jpg" else "image/png",
        })
    return result


def extract_paper_text(paper_path: Path) -> tuple[str, str]:
    """提取论文文本 — 自动适配 PDF 文件或包含 PDF/图片的目录

    Args:
        paper_path: 可以是 .pdf 文件路径，也可以是论文目录

    Returns:
        (format_used, text_content)
        format_used: "pdf" | "images"
    """
    # 直接是 PDF 文件
    if paper_path.is_file() and paper_path.suffix == ".pdf":
        text = extract_from_pdf(paper_path)
        return "pdf", text

    # 目录：优先找 PDF
    if paper_path.is_dir():
        pdfs = list(paper_path.glob("*.pdf"))
        if pdfs:
            text = extract_from_pdf(pdfs[0])
            return "pdf", text

        # 无 PDF，检查图片 — OCR 提取文本
        images = sorted(paper_path.glob("*.jpg")) + sorted(paper_path.glob("*.png"))
        if images:
            text = extract_text_from_images(images)
            return "images", text

    raise FileNotFoundError(f"No PDF or images found: {paper_path}")


def extract_text_from_images(image_paths: list[Path], max_pages: int = 30) -> str:
    """Extract text from paper page images using PyMuPDF OCR or Tesseract.

    Falls back to empty string if no OCR engine is available.
    """
    image_paths = image_paths[:max_pages]
    pages: list[str] = []

    for i, img_path in enumerate(image_paths):
        text = _ocr_single_image(img_path)
        if text.strip():
            pages.append(f"--- Page {i + 1} ---\n{text.strip()}")

    return "\n\n".join(pages)


def _ocr_single_image(img_path: Path) -> str:
    """OCR a single image using PyMuPDF's built-in text extraction.

    PyMuPDF can open image files as single-page documents and extract text
    from embedded text layers, or use Tesseract if available.
    """
    try:
        # PyMuPDF can open images directly as documents
        doc = fitz.open(str(img_path))
        page = doc[0]

        # Try direct text extraction first (works for images with text layers)
        text = page.get_text("text")
        if text.strip():
            doc.close()
            return text

        # Try OCR via Tesseract if available (PyMuPDF >= 1.19 supports this)
        try:
            text = page.get_textpage_ocr(flags=0, full=True).extractText()
            doc.close()
            return text
        except Exception:
            pass

        doc.close()
    except Exception:
        pass

    # Last resort: try pytesseract directly
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(img_path)
        return pytesseract.image_to_string(img)
    except Exception:
        # ImportError (not installed), TesseractNotFoundError (not in PATH), etc.
        pass

    return ""


def get_paper_name(paper_path: Path) -> str:
    """从路径提取干净的论文名称"""
    if paper_path.is_file():
        return paper_path.stem

    name = paper_path.name
    for suffix in ["-逐页转图片(1)", "-逐页转图片", "逐页转图片"]:
        name = name.replace(suffix, "")
    return name.strip()
