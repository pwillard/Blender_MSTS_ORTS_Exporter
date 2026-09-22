@echo off
setlocal

set "OUT=MSTSORTSExporter.pdf"
set "TMP=%TEMP%\MSTSORTSExporter-build-%RANDOM%-%RANDOM%.pdf"

echo Started: %date% %time%
ruby -S asciidoctor-pdf -a pdf-style=resources/pdfstyles/screen-theme.yml -a pdf-fontsdir=fonts book.adoc -b pdf -o "%TMP%"
if errorlevel 1 (
    echo Asciidoctor PDF build failed.
    if exist "%TMP%" del "%TMP%"
    exit /b 1
)

copy /Y "%TMP%" "%OUT%" >nul 2>nul
if errorlevel 1 (
    echo WARNING: Could not replace "%OUT%". It may be open in a PDF viewer.
    echo Fresh PDF left at "%TMP%"
    exit /b 1
)

del "%TMP%"
echo Wrote %OUT%
echo Ended: %date% %time%
