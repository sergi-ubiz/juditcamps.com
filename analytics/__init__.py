"""
Analítica d'audiències pròpia de juditcamps.com (sense cookies ni tercers).

Capes:
  - ``domain``: model d'esdeveniment i regles de negoci (canals, sessions).
  - ``enrich``: enriquiment d'una visita (geolocalització offline, navegador,
    origen del trànsit, detecció de robots).
  - ``store``: persistència (Firestore en producció, SQLite en local).
  - ``report``: càlcul de KPI i agregacions per al tauler.
  - ``routes``: blueprint de Flask (recollida pública i tauler privat).
"""

from analytics.routes import create_analytics_blueprint

__all__ = ["create_analytics_blueprint"]
