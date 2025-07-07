import asyncio
from datetime import datetime, timedelta, timezone

import httpx


async def get_total_pages(owner, repo, base_url, github_token, per_page=100):
    """Get total number of pages from Link header."""

    url = base_url + f"/repos/{owner}/{repo}/pulls"
    headers = {
        'Accept': 'application/vnd.github+json', 
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'MARL-CRAWLER',
    }

    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    params = {
        'per_page': per_page,
        'state': 'closed',
        'page': 1
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print(response.content)
            raise RuntimeError(f"Failed to fetch PRs: {response.status_code}")
        link_header = response.headers.get("Link")
        first_page_data = response.json()

        if not link_header:
            return 1, first_page_data

        for part in link_header.split(','):
            if 'rel="last"' in part:
                last_url = part.split(';')[0].strip().strip("<>")
                last_page = int(httpx.URL(last_url).params["page"])
                return last_page, first_page_data

        return 1, first_page_data


async def get_prs_async(owner, repo,  base_url, github_token):
    per_page = 100
    total_pages, first_page_data = await get_total_pages(owner, repo, base_url=base_url, github_token=github_token, per_page=per_page)

    url = base_url + f"/repos/{owner}/{repo}/pulls"
    headers = {
        'Accept': 'application/vnd.github+json', 
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'MARL-CRAWLER',
    }

    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    async with httpx.AsyncClient(headers=headers) as client:
        tasks = [
            client.get(url, params={"per_page": per_page, "state": "closed", "page": p})
            for p in range(2, total_pages + 1)
        ]

        results = []

        for coro in asyncio.as_completed(tasks):
            resp = await coro
            if resp.status_code == 200:
                results.extend(resp.json())            

    return first_page_data + results


def filter_prs(prs_list, time_delta):
    filtered_list = []

    for pr in prs_list:
        dt = datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        
        if dt > time_delta:
            filtered_list.append(pr["number"])

    return filtered_list



async def _get_single_pr_async(client, owner, repo, pr_id):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_id}"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return pr_id, resp.json()
    except Exception as e:
        print(f"Error fetching PR #{pr_id}: {e}")
    return pr_id, None



def _get_pr_closer(owner, repo, pr_number, base_url, github_token):
    url = base_url + f"/repos/{owner}/{repo}/issues/{pr_number}/events"
    headers = {
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'PR-Tracker',        
    }

    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    response = httpx.get(url, headers=headers)
    if response.status_code != 200:
        print("Error:", response.status_code, response.text)
        return

    events = response.json()
    for event in events:
        if event.get("event") == "closed":
            actor = event.get("actor", {}).get("login")
            return actor

    print(f"No 'closed' event found for PR #{pr_number}")



async def get_maintainers_info_async(owner, repo, pr_list, base_url, github_token):
    maintainers_info = {}
    headers = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'MARL-CRAWLER',        
    }

    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    async with httpx.AsyncClient(headers=headers, timeout=20) as client:
        responses = []
        for coro in asyncio.as_completed([_get_single_pr_async(client, owner, repo, pr_id) for pr_id in pr_list]):
            result = await coro
            responses.append(result)

    for pr_id, pr_info in responses:
        if pr_info is None:
            continue

        is_merged = pr_info['merged']
        maintainer = pr_info['merged_by']['login'] if is_merged else _get_pr_closer(owner, repo, pr_id, base_url=base_url, github_token=github_token)
        state = 'merged' if is_merged else 'closed'

        if maintainer in maintainers_info:
            maintainers_info[maintainer][state] += 1
        else:
            maintainers_info[maintainer] = {'closed': 0, 'merged': 0}
            maintainers_info[maintainer][state] += 1

    total_prs = 0
    for m in maintainers_info:
        total_prs += maintainers_info[m]['closed']+ maintainers_info[m]['merged']


    return maintainers_info
