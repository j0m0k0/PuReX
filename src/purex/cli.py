import click
import asyncio
import json
from purex.prs import fetch_and_filter_prs
from purex.maintainers import fetch_maintainers_summary

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

@click.group()
def get():
    """Get data from GitHub repositories (PRs, maintainers, etc.)"""
    pass

@get.command()
@click.option('--owner', required=True, help='Repository owner.')
@click.option('--repo', required=True, help='Repository name.')
@click.option('--output-file', default='prs.json', help='Where to store the PR list.')
def prs(owner, repo, output_file):
    """Fetch PRs from a repository"""
    prs = asyncio.run(fetch_and_filter_prs(owner, repo))
    with open(output_file, 'w') as f:
        json.dump(prs, f, indent=2)
    click.echo(f"Saved {len(prs)} PRs to {output_file}")

@get.command()
@click.option('--owner', required=True, help='Repository owner.')
@click.option('--repo', required=True, help='Repository name.')
@click.option('--input-file', required=True, help='PR list JSON file from ' + '"purex get prs".')
@click.option('--output-file', default='maintainers.json', help='Where to save maintainers summary.')
def maintainers(owner, repo, input_file, output_file):
    """Get maintainers info from filtered PRs"""
    with open(input_file, 'r') as f:
        prs = json.load(f)

    maintainers_info = asyncio.run(fetch_maintainers_summary(owner, repo, prs))

    with open(output_file, 'w') as f:
        json.dump(maintainers_info, f, indent=2)

    click.echo(f"Saved maintainer info to {output_file}")


cli.add_command(get)
