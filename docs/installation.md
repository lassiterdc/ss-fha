# Installation

## Create environment

```bash
conda create -n ss_fha python=3.11
conda activate ss_fha
```

## Install

```bash
pip install -e ".[docs]"
```

!!! note
    The `[docs]` extra installs MkDocs and mkdocstrings for building documentation locally.
    Omit it for a minimal install: `pip install -e .`
