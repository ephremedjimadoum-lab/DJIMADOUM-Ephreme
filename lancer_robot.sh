#!/bin/sh
# Lanceur pour Mac et Linux : ./lancer_robot.sh
cd "$(dirname "$0")"
[ -f config.env ] || { echo "Copiez config.env.exemple en config.env et mettez-y votre clé API."; exit 1; }
docker image inspect robot-zoom >/dev/null 2>&1 || {
  echo "Première utilisation : installation du robot, comptez 10 à 20 minutes…"
  docker build -t robot-zoom . || exit 1
}
printf "Collez le lien de la réunion Zoom puis appuyez sur Entrée : "; read -r LIEN
printf "Adresse e-mail pour recevoir le compte rendu (laisser vide pour ne pas envoyer) : "; read -r EMAIL
set -- "$LIEN"
[ -n "$EMAIL" ] && set -- "$LIEN" --envoyer-a "$EMAIL"
docker run --rm --env-file config.env -v "$PWD/comptes_rendus:/app/comptes_rendus" -v "$PWD/modeles:/app/modeles" robot-zoom "$@"
echo "Terminé. Le compte rendu se trouve dans le dossier comptes_rendus."
