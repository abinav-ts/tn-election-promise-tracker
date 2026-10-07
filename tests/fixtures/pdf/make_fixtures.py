"""Regenerate the small PDF fixtures: python tests/fixtures/pdf/make_fixtures.py"""

from pathlib import Path

import pymupdf

HERE = Path(__file__).parent

FRONT = (
    "GOVERNMENT OF TAMIL NADU\n"
    "ABSTRACT\n"
    "Scheme - Free bus travel for women - Orders - Issued.\n"
    "Transport Department\n"
    "G.O.(Ms) No.45 Dated: 12.05.2021\n"
)
BODY = (
    "The Government has examined the proposal carefully. The scheme will be implemented in all "
    "town buses operated by the State Transport Undertakings. Women passengers shall travel free. "
)


def text_pdf() -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), FRONT + "\n" + BODY * 6, fontsize=9)
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), BODY * 8 + "\nOrder effective from 01.06.2021.", fontsize=9)
    doc.save(HERE / "text.pdf")


def image_pdf() -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 40, 40), False)
    pix.clear_with(200)
    page.insert_image(pymupdf.Rect(50, 50, 250, 250), pixmap=pix)
    doc.save(HERE / "image_only.pdf")


def corrupt_pdf() -> None:
    (HERE / "corrupt.pdf").write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Catalog >> garbage without xref\n")


if __name__ == "__main__":
    text_pdf()
    image_pdf()
    corrupt_pdf()
