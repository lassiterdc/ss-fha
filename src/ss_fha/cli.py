"""Console script for ss_fha."""

import typer
from rich.console import Console

from ss_fha import utils

app = typer.Typer()
console = Console()


@app.command()
def main() -> None:
    """Console script for ss_fha."""
    console.print("Replace this message by putting your code into "
               "ss_fha.cli.main")
    console.print("See Typer documentation at https://typer.tiangolo.com/")
    utils.do_something_useful()


if __name__ == "__main__":
    app()
