"""Lettura dei PDF dei risultati pubblicati dalla FIN (portale finveneto.org)."""

from .parser import DocumentoFIN, GaraFIN, PDFNonLeggibile, RigaFIN, leggi_pdf

__all__ = ["DocumentoFIN", "GaraFIN", "PDFNonLeggibile", "RigaFIN", "leggi_pdf"]
