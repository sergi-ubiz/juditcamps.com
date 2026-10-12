# Web estàtica de Judit Camps servida amb nginx a Cloud Run
FROM nginx:1.27-alpine

# Configuració personalitzada (port 8080, capçaleres de seguretat, gzip)
COPY nginx.conf /etc/nginx/nginx.conf

# Contingut estàtic del lloc
COPY . /usr/share/nginx/html/

# Elimina del contenidor fitxers que no formen part del lloc públic
RUN rm -rf /usr/share/nginx/html/Dockerfile \
           /usr/share/nginx/html/nginx.conf \
           /usr/share/nginx/html/.dockerignore \
           /usr/share/nginx/html/.git \
           /usr/share/nginx/html/.gitignore \
           /usr/share/nginx/html/assets-src \
           /usr/share/nginx/html/credentials \
           /usr/share/nginx/html/README.md \
           /usr/share/nginx/html/project_context.md

EXPOSE 8080

# nginx en primer pla
CMD ["nginx", "-g", "daemon off;"]
