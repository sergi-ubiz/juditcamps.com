"""
Descarrega la base de dades DB-IP City Lite (CC BY 4.0) en format MMDB.

DB-IP la publica cada mes: es prova el mes actual i, si encara no hi és,
l'anterior. Si no es pot descarregar, la web funciona igual però sense
ubicació a l'analítica.

Ús:
    python scripts/download_geoip.py geo/dbip-city-lite.mmdb
"""

import datetime
import gzip
import os
import shutil
import sys
import urllib.error
import urllib.request

URL_TEMPLATE = "https://download.db-ip.com/free/dbip-city-lite-{month}.mmdb.gz"


def candidate_months(today: datetime.date) -> list[str]:
    """Mes actual i anterior en format AAAA-MM."""
    previous = today.replace(day=1) - datetime.timedelta(days=1)
    return [today.strftime("%Y-%m"), previous.strftime("%Y-%m")]


def download(target_path: str) -> bool:
    """Descarrega i descomprimeix la base de dades; retorna si ha anat bé."""
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    temporary_path = target_path + ".part"
    for month in candidate_months(datetime.date.today()):
        url = URL_TEMPLATE.format(month=month)
        # DB-IP rebutja (403) l'User-Agent per defecte de urllib.
        request = urllib.request.Request(
            url, headers={"User-Agent": "juditcamps.com-build/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=180) as response, \
                    open(temporary_path, "wb") as target:
                shutil.copyfileobj(gzip.GzipFile(fileobj=response), target)
            os.replace(temporary_path, target_path)
            print(f"GeoIP descarregada: {url}")
            return True
        except (urllib.error.URLError, OSError, EOFError) as error:
            print(f"GeoIP no disponible ({url}): {error}")
    if os.path.exists(temporary_path):
        os.remove(temporary_path)
    return False


if __name__ == "__main__":
    destination = sys.argv[1] if len(sys.argv) > 1 else "geo/dbip-city-lite.mmdb"
    download(destination)
