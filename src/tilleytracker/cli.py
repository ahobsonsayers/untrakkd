import typer
import uvicorn

VERSION = "0.1.0"

cli = typer.Typer(name="***tracker", help="***tracker cli", no_args_is_help=True)


@cli.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind"),
    port: int = typer.Option(8000, help="Port to bind"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
) -> None:
    uvicorn.run("***tracker.app:app", host=host, port=port, reload=reload)


@cli.command()
def fetch() -> None:
    """Scrape ***'s Untappd history into events.json."""
    from .scraper import main as scrape

    scrape()


@cli.command()
def version() -> None:
    typer.echo(VERSION)


if __name__ == "__main__":
    cli()
