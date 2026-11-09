"""Fixture comuni.

I test unitari non toccano database ne' rete. I test d'integrazione su MySQL
partono solo con ``RANAZZURRA_TEST_MYSQL=1`` e le variabili ``MYSQL_*`` di un
server di prova: creano un database usa-e-getta (``ranazzurra_test``), non
usano mai quello configurato in secrets.toml.

Il PDF reale di prova (contiene nomi di minori, quindi non e' nel repository)
si indica con ``RANAZZURRA_PDF_TEST`` oppure si mette in
``tests/fixtures_privati/riepilogo_20261108.pdf``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))


@pytest.fixture
def pdf_reale() -> bytes:
    p = Path(os.environ.get("RANAZZURRA_PDF_TEST", RADICE / "tests" / "fixtures_privati" / "riepilogo_20261108.pdf"))
    if not p.exists():
        pytest.skip("PDF reale di prova non disponibile")
    return p.read_bytes()


def crea_pdf(pagine: list[list[str]]) -> bytes:
    """PDF sintetico con una riga di testo per riga indicata (serve reportlab,
    solo come dipendenza di sviluppo)."""
    pytest.importorskip("reportlab")
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for righe in pagine:
        y = 800
        for r in righe:
            c.setFont("Helvetica", 8)
            c.drawString(20, y, r)
            y -= 12
        c.showPage()
    c.save()
    return buf.getvalue()
