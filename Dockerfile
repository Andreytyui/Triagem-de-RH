# Imagem única do produto. Já traz o LibreOffice, que é o que permite ler
# currículo em .doc e .rtf antigos — formato ainda comum em RH no Brasil.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TRIAGEM_DATA_DIR=/dados

# Duas dependências de sistema, pelo mesmo motivo: currículo chega como chega.
# O LibreOffice lê o .doc velho; o Tesseract lê o que veio do scanner, que é
# cerca de 10% do que este recrutador recebe.
#
# O pacote do LibreOffice sem interface gráfica é bem menor; nem toda base tem
# esse nome, daí a alternativa. As conferências no fim fazem a build falhar aqui
# e agora se algo não ficou no lugar — melhor que descobrir no primeiro .doc ou
# no primeiro currículo digitalizado do cliente.
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-dejavu-core curl \
      tesseract-ocr tesseract-ocr-por \
 && (apt-get install -y --no-install-recommends libreoffice-writer-nogui \
     || apt-get install -y --no-install-recommends libreoffice-writer) \
 && rm -rf /var/lib/apt/lists/* \
 && command -v soffice \
 && command -v tesseract \
 && tesseract --list-langs | grep -qx por

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY static/ ./static/

# O servidor não roda como root, e os dados moram num volume separado do código.
RUN useradd --create-home --uid 10001 triagem \
 && mkdir -p /dados \
 && chown -R triagem:triagem /dados /app
USER triagem
VOLUME ["/dados"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/saude || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
