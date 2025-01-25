REM Run this script to create the installer file
REM Create the git hash file used by the installed apps to indicate the src git hash
git rev-parse --short HEAD > ../assets/git_hash.txt
REM Run innosetup to create the installer files in the ../installers folder.
"C:\Program Files (x86)\Inno Setup 6\iscc.exe" rs310p-dc-psu.iss
