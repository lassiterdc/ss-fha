# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'ss-fha'
copyright = '2026, Daniel Lassiter'
author = 'Daniel Lassiter'
release = '0.1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",  # for Google/NumPy style docstrings
	"nbsphinx", # for jupyter hosting jupyter notebooks
    "sphinx.ext.mathjax",  # optional, if you use math
    "sphinxcontrib.mermaid" # for mermaid docs
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ['_static']

mermaid_init_js = """
mermaid.initialize({
  theme: 'default',
  flowchart: { useMaxWidth: true }
});
"""