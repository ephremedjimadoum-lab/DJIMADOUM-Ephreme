# Robot Zoom de prise de notes : navigateur, écran virtuel, son virtuel et transcription locale.
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends pulseaudio ffmpeg xvfb xauth \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt faster-whisper playwright==1.55.0 \
    && playwright install --with-deps chromium

# Le modèle de transcription est téléchargé une seule fois et conservé dans ce dossier.
ENV HF_HOME=/app/modeles
COPY agent_compte_rendu ./agent_compte_rendu
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]
