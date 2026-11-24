@echo off
rem Met à jour l'atlas ergo : télécharge les nouvelles éditions des sources et recalcule si besoin. Lancé chaque mois par la tâche planifiée ; on peut aussi double-cliquer dessus.
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "CONDA="
for %%D in ("%USERPROFILE%\anaconda3" "%USERPROFILE%\miniconda3" "%LOCALAPPDATA%\anaconda3" "%ProgramData%\anaconda3" "%ProgramData%\miniconda3") do if exist "%%~D\Scripts\activate.bat" set "CONDA=%%~D"
if not defined CONDA (
  echo Anaconda introuvable : corriger le chemin dans mise_a_jour.bat
  exit /b 1
)
call "%CONDA%\Scripts\activate.bat" base
if not exist donnees mkdir donnees
python chaine\lancer.py %* >> donnees\mise_a_jour.log 2>&1
echo Fini, voir donnees\mise_a_jour.log
