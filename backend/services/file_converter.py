"""文件转换服务

将 PDF/Word 批量转换为图片，自动删除空白页。
已存在对应图片则跳过转换。
"""

import os
import logging
from pathlib import Path
from typing import Callable

from PIL import Image

logger = logging.getLogger(__name__)

# 空白页判定阈值：灰度值 > 250 的像素占比超过此值视为空白
BLANK_THRESHOLD = 0.999


def is_blank_image(image_path: Path) -> bool:
    """检测图片是否为空白页（缩略图快速检测）"""
    try:
        img = Image.open(image_path).convert("L")
        # 缩放到 500px 宽以加速检测
        w, h = img.size
        if w > 500:
            ratio = 500 / w
            img = img.resize((500, int(h * ratio)), Image.LANCZOS)
        pixels = list(img.getdata())
        white_count = sum(1 for p in pixels if p > 250)
        return (white_count / len(pixels)) > BLANK_THRESHOLD
    except Exception:
        return False


def convert_pdf_to_images(pdf_path: Path, output_dir: Path, dpi: int = 200,
                          progress_cb: Callable | None = None) -> list[Path]:
    """将 PDF 每页转为图片，跳过空白页

    Returns:
        非空白页图片路径列表
    """
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    images = []
    total = len(doc)

    for i in range(total):
        page = doc[i]
        pix = page.get_pixmap(dpi=dpi)
        img_path = output_dir / f"{pdf_path.stem}_p{i + 1:03d}.jpg"
        pix.save(str(img_path))

        if is_blank_image(img_path):
            img_path.unlink()
            logger.debug(f"删除空白页: {img_path.name}")
        else:
            images.append(img_path)

        if progress_cb:
            progress_cb(i + 1, total)

    doc.close()
    logger.info(f"PDF 转换完成: {pdf_path.name} → {len(images)} 页 (跳过 {total - len(images)} 空白页)")
    return images


def convert_docx_to_images(docx_path: Path, output_dir: Path, dpi: int = 200) -> list[Path]:
    """将 Word 转为图片（先转 PDF 再转图片），跳过空白页"""
    pdf_path = output_dir / f"{docx_path.stem}_temp.pdf"

    # Step 1: Word → PDF
    _docx_to_pdf(docx_path, pdf_path)

    if not pdf_path.exists():
        raise RuntimeError(f"Word 转 PDF 失败: {docx_path.name}")

    # Step 2: PDF → 图片
    images = convert_pdf_to_images(pdf_path, output_dir, dpi)

    # 清理临时 PDF
    try:
        pdf_path.unlink()
    except Exception:
        pass

    logger.info(f"Word 转换完成: {docx_path.name} → {len(images)} 页")
    return images


def _docx_to_pdf(docx_path: Path, pdf_path: Path):
    """Word → PDF（尝试多种方式）"""
    # 方式 1: docx2pdf（需要 MS Word）
    try:
        from docx2pdf import convert
        convert(str(docx_path), str(pdf_path))
        return
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"docx2pdf 失败: {e}")

    # 方式 2: win32com（需要 MS Word）
    try:
        import win32com.client
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(str(docx_path.resolve()))
        doc.SaveAs(str(pdf_path.resolve()), FileFormat=17)  # 17 = PDF
        doc.Close()
        word.Quit()
        return
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"win32com 失败: {e}")

    # 方式 3: LibreOffice headless
    try:
        import subprocess
        subprocess.run([
            "libreoffice", "--headless", "--convert-to", "pdf",
            "--outdir", str(pdf_path.parent),
            str(docx_path),
        ], check=True, timeout=60)
        return
    except Exception as e:
        logger.debug(f"LibreOffice 失败: {e}")

    raise RuntimeError(
        "Word 转 PDF 需要以下任一工具:\n"
        "  1. 安装 MS Word + pip install docx2pdf pywin32\n"
        "  2. 安装 LibreOffice (免费)\n"
        "  或将 Word 另存为 PDF 后上传"
    )


def scan_and_convert(folder: str, output_dir: str | None = None,
                     progress_cb: Callable | None = None) -> list[Path]:
    """扫描文件夹，转换所有 PDF/Word，返回图片列表

    - 如果 PDF/Word 已有对应图片则跳过
    - 自动删除空白页

    Args:
        folder: 源文件夹路径
        output_dir: 输出目录，默认与源文件夹相同
        progress_cb: 进度回调 (current, total, filename)

    Returns:
        所有图片文件路径列表
    """
    folder = Path(folder)
    out = Path(output_dir) if output_dir else folder
    out.mkdir(parents=True, exist_ok=True)

    # 收集所有需要转换的文件
    pdf_files = list(folder.glob("*.pdf"))
    docx_files = list(folder.glob("*.docx")) + list(folder.glob("*.doc"))
    image_files = list(folder.glob("*.jpg")) + list(folder.glob("*.jpeg")) + list(folder.glob("*.png"))

    all_images = []
    total = len(pdf_files) + len(docx_files)

    # 已有的图片直接加入
    for img in image_files:
        if not is_blank_image(img):
            all_images.append(img)
        else:
            img.unlink()
            logger.debug(f"删除空白图片: {img.name}")

    processed = len(image_files)

    # 转换 PDF
    for pdf in pdf_files:
        # 检查是否已有对应的图片
        existing = list(out.glob(f"{pdf.stem}_p*.jpg"))
        if existing:
            logger.info(f"跳过已有图片: {pdf.name}")
            all_images.extend(existing)
            continue

        try:
            imgs = convert_pdf_to_images(pdf, out)
            all_images.extend(imgs)
        except Exception as e:
            logger.error(f"PDF 转换失败: {pdf.name}: {e}")

        processed += 1
        if progress_cb:
            progress_cb(processed, total + len(image_files), pdf.name)

    # 转换 Word
    for docx in docx_files:
        existing = list(out.glob(f"{docx.stem}_p*.jpg"))
        if existing:
            logger.info(f"跳过已有图片: {docx.name}")
            all_images.extend(existing)
            continue

        try:
            imgs = convert_docx_to_images(docx, out)
            all_images.extend(imgs)
        except Exception as e:
            logger.error(f"Word 转换失败: {docx.name}: {e}")

        processed += 1
        if progress_cb:
            progress_cb(processed, total + len(image_files), docx.name)

    logger.info(f"文件夹扫描完成: {len(all_images)} 张图片（转换 {len(pdf_files)} PDF + {len(docx_files)} Word）")
    return all_images
