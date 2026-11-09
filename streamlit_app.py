"""
Ranazzurra Records Manager: record societari della squadra agonistica di
categoria di Ranazzurra Conegliano SSD.

Entrypoint per Streamlit Community Cloud. La logica sta nel pacchetto
``ranazzurra_records``; qui ci sono solo configurazione della pagina, menu
e instradamento verso le pagine in ``ranazzurra_records/views``.
"""

import logging

import streamlit as st
from mysql.connector import Error as MySQLError

from ranazzurra_records import __version__
from ranazzurra_records.config import ConfigurazioneMancante
from ranazzurra_records.views import atleti, comuni, dashboard, importa, personali, top3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

st.set_page_config(
    page_title="Ranazzurra Records Manager",
    page_icon="🏊",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(comuni.CSS, unsafe_allow_html=True)

PAGINE = {
    "🏠 Dashboard": dashboard.mostra,
    "🏆 Record Top 3": top3.mostra,
    "👤 Gestione Atleti": atleti.mostra,
    "🏅 Gestione Record": personali.mostra,
    "📥 Importa risultati FIN": importa.mostra,
}


def main() -> None:
    with st.sidebar:
        scelta = st.radio("🧭 Menu", list(PAGINE), key="menu_nav")
        st.markdown("---")
        st.markdown(
            f"**Ranazzurra Conegliano**  \nRecord societari · squadra di categoria  \n"
            f"Database: MySQL (Aiven)  \nVersione {__version__}"
        )
        if st.button("🔄 Aggiorna dati", key="refresh_btn"):
            st.cache_data.clear()
            st.rerun()
    try:
        PAGINE[scelta]()
    except ConfigurazioneMancante as e:
        st.error(f"⚙️ {e}")
    except MySQLError as e:
        logging.exception("Errore database")
        st.error(
            "❌ Il database non risponde o ha restituito un errore. Se il servizio Aiven e' "
            f"spento va riacceso dalla console. Dettaglio: {e}"
        )


main()
