#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""LabelImg entry point for package execution."""

import sys
import os

# Adiciona o diretório do pacote ao path para permitir imports absolutos legados
package_dir = os.path.dirname(os.path.abspath(__file__))
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

# Importa do módulo labelImg (arquivo labelImg.py)
from labelImg import main as app_main


def main():
    """Entry point wrapper."""
    return app_main()


if __name__ == "__main__":
    sys.exit(main())
