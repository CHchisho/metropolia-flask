"""Build minimal text PDFs without extra dependencies (used by tests and the sample PDF script)."""
from __future__ import annotations

import textwrap


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[str]) -> bytes:
    """One page per string; paragraphs separated by blank lines. Latin-1 characters only."""
    objects: list[bytes] = []  # object number = index + 1

    font_no = 3 + 2 * len(pages)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())

    for i, text in enumerate(pages):
        lines: list[str] = []
        for paragraph in text.split("\n\n"):
            lines.extend(textwrap.wrap(paragraph.replace("\n", " "), 90) or [""])
            lines.append("")
        stream = ["BT", "/F1 11 Tf", "14 TL", "50 790 Td"]
        stream += [f"({_escape(line)}) '" for line in lines]
        stream.append("ET")
        content = "\n".join(stream).encode("latin-1", "replace")
        content_no = 4 + 2 * i
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_no} 0 R >> >> /Contents {content_no} 0 R >>".encode()
        )
        objects.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
