
import httpx
import asyncio




from rich.progress import Progress, SpinnerColumn, BarColumn, TimeElapsedColumn, TextColumn



from datetime import datetime, timedelta, timezone

import os

# Constants
BASE_URL = "https://api.github.com"
try:
    GITHUB_TOKEN = os.environ["PUREX_TOKEN"]
except KeyError:
    print("The PUREX_TOKEN token should be set, before using the tool.")
    exit(0)

HEADERS = {
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'PUREX-AGENT',
    'Authorization': f'Bearer {GITHUB_TOKEN}',
}
DAYS = 14
NOW = datetime.now(timezone.utc)
SINCE = NOW - timedelta(days=DAYS)

# --------------- PR FETCHING -------------------

async def get_total_pages(owner, repo, per_page=100):
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls"
    params = {'per_page': per_page, 'state': 'closed', 'page': 1}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        link_header = response.headers.get("Link")
        first_page_data = response.json()

        if not link_header:
            return 1, first_page_data

        for part in link_header.split(','):
            if 'rel="last"' in part:
                last_url = part.split(';')[0].strip('<> ')
                last_page = int(httpx.URL(last_url).params["page"])
                return last_page, first_page_data
        return 1, first_page_data

async def get_prs_async(owner, repo):
    per_page = 100
    total_pages, first_page_data = await get_total_pages(owner, repo, per_page)
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls"

    async with httpx.AsyncClient(headers=HEADERS) as client:
        tasks = [
            client.get(url, params={'per_page': per_page, 'state': 'closed', 'page': p})
            for p in range(2, total_pages + 1)
        ]

        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
            BarColumn(), "[progress.percentage]{task.percentage:>3.0f}%",
            TimeElapsedColumn(), transient=True
        ) as progress:
            task = progress.add_task("[cyan]Fetching PRs...", total=len(tasks))
            results = []

            for coro in asyncio.as_completed(tasks):
                resp = await coro
                if resp.status_code == 200:
                    results.extend(resp.json())
                progress.advance(task)

    return first_page_data + results

def filter_prs(prs):
    """Return list of PR numbers created within the last `DAYS`."""
    result = []
    for pr in prs:
        created = datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if created > SINCE:
            result.append(pr["number"])
    return result

# --------------- MAINTAINER ANALYSIS -------------------

async def _get_single_pr_async(client, owner, repo, pr_id):
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_id}"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return pr_id, resp.json()
    except Exception as e:
        print(f"Error fetching PR #{pr_id}: {e}")
    return pr_id, None

def _get_pr_closer(owner, repo, pr_number):
    url = f"{BASE_URL}/repos/{owner}/{repo}/issues/{pr_number}/events"
    response = httpx.get(url, headers=HEADERS)
    if response.status_code != 200:
        return None
    for event in response.json():
        if event.get("event") == "closed":
            return event.get("actor", {}).get("login")
    return None

async def get_maintainers_info_async(owner, repo, pr_list):
    maintainers_info = {}

    async with httpx.AsyncClient(headers=HEADERS, timeout=20) as client:
        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
            BarColumn(), "[progress.percentage]{task.percentage:>3.0f}%",
            TimeElapsedColumn(), transient=True
        ) as progress:
            task = progress.add_task("[cyan]Fetching PR details...", total=len(pr_list))
            responses = []
            for coro in asyncio.as_completed([
                _get_single_pr_async(client, owner, repo, pr_id) for pr_id in pr_list
            ]):
                result = await coro
                responses.append(result)
                progress.advance(task)

    for pr_id, pr in responses:
        if pr is None:
            continue
        is_merged = pr.get("merged", False)
        maintainer = (
            pr["merged_by"]["login"] if is_merged else _get_pr_closer(owner, repo, pr_id)
        )
        state = "merged" if is_merged else "closed"
        if not maintainer:
            continue
        if maintainer not in maintainers_info:
            maintainers_info[maintainer] = {'closed': 0, 'merged': 0}
        maintainers_info[maintainer][state] += 1

    total = sum(v['closed'] + v['merged'] for v in maintainers_info.values())
    print(f"Total PRs merged or closed in last {DAYS} days: {total}")
    return maintainers_info
