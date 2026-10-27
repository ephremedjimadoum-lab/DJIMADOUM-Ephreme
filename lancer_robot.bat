@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist config.env (
  echo Fichier config.env introuvable : copiez config.env.exemple en config.env et mettez-y votre cle API.
  pause
  exit /b 1
)
docker image inspect robot-zoom >nul 2>&1 || (
  echo Premiere utilisation : installation du robot, comptez 10 a 20 minutes...
  docker build -t robot-zoom . || (pause & exit /b 1)
)
set /p LIEN=Collez le lien de la reunion Zoom puis appuyez sur Entree : 
set /p EMAIL=Adresse e-mail pour recevoir le compte rendu (laisser vide pour ne pas envoyer) : 
set OPTIONS=
if not "%EMAIL%"=="" set OPTIONS=--envoyer-a %EMAIL%
docker run --rm --env-file config.env -v "%cd%\comptes_rendus:/app/comptes_rendus" -v "%cd%\modeles:/app/modeles" robot-zoom "%LIEN%" %OPTIONS%
echo.
echo Termine. Le compte rendu se trouve dans le dossier comptes_rendus.
start "" comptes_rendus
pause
