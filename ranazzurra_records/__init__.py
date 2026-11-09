"""Ranazzurra Records: gestione dei record societari della squadra agonistica
di categoria di Ranazzurra Conegliano SSD.

Il pacchetto separa la logica (tempi, record, parser PDF FIN, importazione)
dall'interfaccia Streamlit, che sta in ``ranazzurra_records.views``.
I moduli di dominio non importano ``streamlit``: si provano da terminale.
"""

__version__ = "2.0.0"
