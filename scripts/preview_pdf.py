"""开发用：把 PDF 每页渲染成 PNG，便于肉眼检查排版。"""

from __future__ import annotations

import sys
from pathlib import Path

import pypdfium2 as pdfium


def main() -> int:
    pdf_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else pdf_path.with_suffix("")
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = pdfium.PdfDocument(str(pdf_path))
    for index in range(len(doc)):
        page = doc[index]
        image = page.render(scale=1.6).to_pil()
        target = out_dir / f"page-{index + 1}.png"
        image.save(target)
        print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
