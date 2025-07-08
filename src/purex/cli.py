import asyncio
import os
from datetime import date, datetime, timezone
from importlib.metadata import PackageNotFoundError, version

import click

from .core import filter_prs, get_maintainers_info_async, get_prs_async

try:
    __version__ = version("purex")  # match your [project.name]
except PackageNotFoundError:
    __version__ = "unknown"


@click.group()
@click.version_option(__version__, prog_name='purex')
def cli():
    pass

@cli.command(short_help="Get pull-request data of a repository.")
@click.argument("owner", nargs=1)
@click.argument("repository", nargs=1)
@click.option("--token", "-t", "token", default=None, help="GitHub Token")
@click.option("--base_url", "-u", "base_url", default="https://api.github.com", help="REST API url of GitHub.")
@click.option(
    "--start_date",
    type=click.DateTime(formats=["%m-%d-%Y"]),
    default=date.today().strftime("%m-%d-%Y"),
    help="Inclusive starting date (MM-DD-YYYY) for pulling the pull-request data."
)
def get(owner, repository, token, start_date, base_url):
    """GET pull-request data for REPOSITY from OWNER.

    OWNER is the account name that hosts the repository (e.g., torvalds).
    
    REPOSITORY is the name of the repository (e.g., linux)."""

    token = token or os.getenv("PUREX_TOKEN")
    # start_date = start_date if start_date else 
    time_delta = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)    

    all_prs = asyncio.run(get_prs_async(owner, repository, base_url, token))
    processed_PRs = filter_prs(all_prs, time_delta)
    maintainers_info = asyncio.run(get_maintainers_info_async(owner, repository, processed_PRs, base_url, token))

    print(maintainers_info)
