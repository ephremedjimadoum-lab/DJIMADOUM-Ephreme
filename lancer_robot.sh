#!/bin/sh
# Lanceur pour Mac et Linux : ./lancer_robot.sh
cd "$(dirname "$0")"
[ -f config.env ] && grep -q "sk-ant-collez" config.env && rm config.env
if [ ! -f config.env ]; then
  printf "Collez votre clé API Claude (elle commence par sk-ant-) puis appuyez sur Entrée : "; read -r CLE
  [ -n "$CLE" ] || { echo "Aucune clé saisie."; exit 1; }
  echo "ANTHROPIC_API_KEY=$CLE" > config.env
fi
docker info >/dev/null 2>&1 || { echo "Docker Desktop n'est pas démarré : ouvrez-le puis relancez."; exit 1; }
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
