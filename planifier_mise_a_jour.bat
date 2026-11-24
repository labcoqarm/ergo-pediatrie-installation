@echo off
rem À lancer une seule fois : crée une tâche Windows qui lance mise_a_jour.bat le 1er de chaque mois à 11 h. Quand il n'y a rien de neuf, elle s'arrête en quelques secondes.
schtasks /Create /F /TN "Ergo pediatrie mise a jour" /SC MONTHLY /D 1 /ST 11:00 /TR "\"%~dp0mise_a_jour.bat\""
if errorlevel 1 (echo La tache n'a pas pu etre creee.) else (echo Tache creee. Pour la retirer : schtasks /Delete /TN "Ergo pediatrie mise a jour")
pause
