# Web de Judit Camps: nginx (estàtic) + gunicorn/Flask (formulari) a Cloud Run
FROM python:3.12-slim

# nginx per servir l'estàtic i fer de proxy a l'API
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx gettext-base \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependències de Python del backend
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Codi del backend
COPY app.py /app/app.py

# Configuració d'nginx i entrypoint
COPY nginx.conf /etc/nginx/nginx.conf
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Contingut estàtic del lloc
COPY . /usr/share/nginx/html/

# Elimina del directori públic fitxers que no formen part del lloc
RUN rm -rf /usr/share/nginx/html/Dockerfile \
           /usr/share/nginx/html/nginx.conf \
           /usr/share/nginx/html/entrypoint.sh \
           /usr/share/nginx/html/app.py \
           /usr/share/nginx/html/requirements.txt \
           /usr/share/nginx/html/.dockerignore \
           /usr/share/nginx/html/.git \
           /usr/share/nginx/html/.gitignore \
           /usr/share/nginx/html/assets-src \
           /usr/share/nginx/html/credentials \
           /usr/share/nginx/html/README.md \
           /usr/share/nginx/html/project_context.md \
           /usr/share/nginx/html/__pycache__

EXPOSE 8080

CMD ["/app/entrypoint.sh"]
