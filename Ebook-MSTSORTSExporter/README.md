# Ebook-MSTSORTSExporter
AsciiDoctor source for the Blender MSTS/Open Rails exporter documentation.


AsciiDoctor Source code, license CC-BY-SA-4.0

The generated PDF is distributed in the main exporter documentation package.


# To BUILD this document from AsciiDoctor source you need:

## Install Ruby

Have the RUBY programming language installed.   https://rubyinstaller.org/

## Install AsciiDoctor - pre-release

Install AsciiDoctor-PDF with the following command: `gem install asciidoctor-pdf`

## Install Rouge syntax highlighter

Install Rouge with the following command: `gem install rouge`

## Install AsciiDoctor Diagram

Install the diagram tool with the following command: `gem install asciidoctor-diagram`

## Assembling the document

Use the following command to create the PDF document output:


ruby -S asciidoctor-pdf -a pdf-style=resources/pdfstyles/screen-theme.yml -a pdf-fontsdir=fonts book.adoc -b pdf -o MSTSORTSExporter.pdf

NOTE: ASCIIDOCTOR formatting code is ALMOST github compatible...  so GITHUB tries to render it... (It just doesn't really work)


You can use the script `makeit.bat` to convert the document to PDF.
