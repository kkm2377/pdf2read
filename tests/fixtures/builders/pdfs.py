from __future__ import annotations

from pathlib import Path

import pymupdf


def _save(doc, path: Path, title: str = "Synthetic document") -> Path:
    doc.set_metadata({"title": title})
    doc.set_toc([(1, title, 1)])
    doc.save(path)
    doc.close()
    return path


def build_selectable_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=595)
    page.insert_text((42, 65), "Synthetic selectable document", fontsize=18)
    for i in range(12):
        page.insert_text(
            (42, 100 + i * 25),
            f"Paragraph line {i}: selectable text remains in reading order.",
            fontsize=10,
        )
    return _save(doc, path)


def build_scan_pdf(path: Path) -> Path:
    source = pymupdf.open()
    page = source.new_page(width=420, height=595)
    for i in range(10):
        page.insert_text((45, 80 + i * 32), f"Scanned pixel line {i}", fontsize=16)
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
    doc = pymupdf.open()
    target = doc.new_page(width=420, height=595)
    target.insert_image(target.rect, pixmap=pixmap)
    source.close()
    return _save(doc, path, "Synthetic scan")


def build_two_column_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=595)
    page.insert_text((40, 55), "Main article", fontsize=16)
    for i in range(14):
        page.insert_text((40, 90 + i * 24), f"Main body line {i} stays left.", fontsize=9)
    for i in range(10):
        page.insert_text((315, 100 + i * 22), f"Note {i}", fontsize=7)
    return _save(doc, path, "Two column notes")


def build_two_up_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=595)
    for i in range(16):
        page.insert_text((40, 55 + i * 25), f"Left item {i}", fontsize=8)
        page.insert_text((225, 55 + i * 25), f"Right item {i}", fontsize=8)
    return _save(doc, path, "Dense two-up")


def build_table_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=595)
    x0, y0, cell_w, cell_h = 45, 100, 105, 42
    for row in range(4):
        page.draw_line((x0, y0 + row * cell_h), (x0 + cell_w * 3, y0 + row * cell_h))
    for col in range(4):
        page.draw_line((x0 + col * cell_w, y0), (x0 + col * cell_w, y0 + cell_h * 3))
    values = [
        ["Name", "Value", "Status"],
        ["Alpha", "10", "Open"],
        ["Beta", "20", "Closed"],
    ]
    for row, cells in enumerate(values):
        for col, value in enumerate(cells):
            page.insert_text(
                (x0 + col * cell_w + 8, y0 + row * cell_h + 25),
                value,
                fontsize=9,
            )
    return _save(doc, path, "Synthetic table")


def build_math_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=595)
    page.insert_text((42, 70), "Formula examples", fontsize=18)
    page.insert_text((60, 130), "E = mc2", fontsize=14)
    page.insert_text((60, 175), "f(x) = (a + b) / sqrt(c)", fontsize=14)
    page.insert_text((60, 220), "P(A | B) = P(B | A) P(A) / P(B)", fontsize=14)
    return _save(doc, path, "Synthetic formulas")


def build_figure_wrap_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=595)
    page.insert_text((42, 65), "Figure and surrounding body", fontsize=16)
    page.insert_text((42, 100), "Body before the figure must remain selectable.", fontsize=9)
    page.draw_rect((130, 145, 300, 300), color=(0.7, 0.25, 0.1), fill=(0.95, 0.85, 0.7))
    page.draw_circle((215, 222), 45, color=(0.3, 0.3, 0.3))
    page.insert_text((165, 225), "Diagram", fontsize=10)
    page.insert_text((42, 165), "Wrapped body on the left.", fontsize=9)
    page.insert_text((42, 330), "Body after the figure must remain selectable.", fontsize=9)
    page.insert_text((175, 315), "Figure 1", fontsize=8)
    return _save(doc, path, "Synthetic figure")


def build_exam_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=595)
    font = "japan-s"
    page.insert_text((45, 65), "問", fontsize=11, fontname=font)
    page.insert_text((63, 52), "1", fontsize=24, fontname=font)
    page.insert_text((45, 105), "適切なものはどれか。", fontsize=10, fontname=font)
    choices = [
        ("ア", "最初の選択肢です。"),
        ("イ", "二番目の選択肢です。"),
        ("ウ", "三番目の選択肢です。"),
        ("エ", "四番目の選択肢です。"),
    ]
    for i, (mark, text) in enumerate(choices):
        page.insert_text((55, 145 + i * 45), f"{mark}　{text}", fontsize=10, fontname=font)
    return _save(doc, path, "Synthetic exam")


def build_vertical_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=595)
    for i in range(8):
        page.insert_text(
            (80 + i * 32, 500),
            f"Vertical line {i}",
            fontsize=10,
            rotate=90,
        )
    return _save(doc, path, "Synthetic vertical")


def build_mixed_pdf(path: Path) -> Path:
    scan_path = path.with_name("scan-source.pdf")
    build_scan_pdf(scan_path)
    scan = pymupdf.open(scan_path)
    pixmap = scan[0].get_pixmap()
    doc = pymupdf.open()
    first = doc.new_page(width=420, height=595)
    first.insert_text((42, 80), "Normal selectable first page " * 4, fontsize=10)
    second = doc.new_page(width=420, height=595)
    second.insert_image(second.rect, pixmap=pixmap)
    scan.close()
    scan_path.unlink()
    return _save(doc, path, "Synthetic mixed")


def build_large_pdf(path: Path, pages: int = 200) -> Path:
    doc = pymupdf.open()
    toc = []
    for page_number in range(1, pages + 1):
        page = doc.new_page(width=420, height=595)
        page.insert_text((42, 60), f"Synthetic section {page_number}", fontsize=16)
        for line in range(8):
            page.insert_text(
                (42, 100 + line * 30),
                f"Page {page_number} line {line} remains readable and ordered.",
                fontsize=10,
            )
        if page_number == 1 or page_number % 10 == 0:
            toc.append((1, f"Section {page_number}", page_number))
    doc.set_metadata({"title": "Synthetic large document"})
    doc.set_toc(toc)
    doc.save(path)
    doc.close()
    return path


def build_encrypted_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 80), "Encrypted synthetic content", fontsize=12)
    doc.save(
        path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="reader-password",
    )
    doc.close()
    return path


def build_corrupt_pdf(path: Path) -> Path:
    build_selectable_pdf(path)
    data = path.read_bytes()
    path.write_bytes(data[: max(32, len(data) // 3)])
    return path
