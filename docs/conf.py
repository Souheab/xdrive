# Configuration file for the Sphinx documentation builder.

import os
import sys

# -- Path setup ---------------------------------------------------------------
sys.path.insert(0, os.path.abspath(".."))

# -- Project information ------------------------------------------------------
project = "xdrive"
copyright = "2026, xdrive contributors"
author = "xdrive contributors"
release = "0.1.0"

# -- General configuration ----------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Napoleon settings --------------------------------------------------------
napoleon_google_docstring = True
napoleon_numpy_docstring = False

# -- Autodoc settings ---------------------------------------------------------
autodoc_member_order = "bysource"
autodoc_typehints = "description"

# -- MyST settings ------------------------------------------------------------
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# -- HTML output --------------------------------------------------------------
html_theme = "furo"
html_static_path = ["_static"]
