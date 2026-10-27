@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem --- Configuration : cle API Claude ---
if exist config.env.txt if not exist config.env ren config.env.txt config.env
if exist config.env findstr /c:"sk-ant-collez" config.env >nul && del config.env
if exist config.env goto config_ok
echo.
echo === Premiere configuration ===
echo Votre cle API Claude se cree sur https://console.anthropic.com (menu API Keys).
echo.
set /p CLE=Collez votre cle API Claude (elle commence par sk-ant-) puis appuyez sur Entree : 
if "%CLE%"=="" (
  echo Aucune cle saisie.
  pause
  exit /b 1
)
> config.env echo ANTHROPIC_API_KEY=%CLE%
echo Cle enregistree dans config.env.
:config_ok

rem --- Docker doit etre demarre ---
docker info >nul 2>&1 || (
  echo Docker Desktop n'est pas demarre : ouvrez-le, attendez "Engine running", puis relancez ce fichier.
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
if exist comptes_rendus start "" comptes_rendus
pause
