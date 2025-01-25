#!/bin/bash
# Ensure we remove old installer versions.
rm -rf dist
set -e
# syntax checking
pyflakes3 rs310p_dc_psu/*.py
# code style checking
pycodestyle --max-line-length=250 rs310p_dc_psu/*.py
poetry -vvv build
cp dist/*.whl installers


