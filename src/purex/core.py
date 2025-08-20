import asyncio
from datetime import datetime, timezone

import httpx

BASE_HEADERS = {
    'Accept': 'application/vnd.github+json', 
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'MARL-CRAWLER',
}

async def get_total_num_pages(owner, repo, base_url, github_token, per_page=100):
    """Gets total number of pages for pagination purposes

    Args:
        owner (str): Repository owner
        repo (str): Repository name
        base_url (str): Base GitHub URL
        github_token (str): GitHub API Token
        per_page (int, optional): Number of PR items per page. Defaults to 100.

    Raises:
        RuntimeError: Raises when the first request doesn't respond with 200 status code

    Returns:
        tuple: number of pages, first page data
    """

    url = base_url + f"/repos/{owner}/{repo}/pulls"
    headers = BASE_HEADERS

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


async def get_prs_async(owner, repo,  base_url, github_token, per_page = 100):
    """Fetch all closed pull requests from a GitHub repository using async pagination.

    Args:
        owner (str): The GitHub account or organization name that owns the repository.
        repo (str): The name of the repository to fetch pull requests from.
        base_url (str): The base URL of the GitHub REST API (e.g., "https://api.github.com").
        github_token (str): Personal access token for authentication. If None, requests
            will be unauthenticated and subject to stricter rate limits.
        per_page (int, optional): Number of pull requests to fetch per page.
            Maximum allowed by GitHub is 100. Defaults to 100.

    Returns:
        list[dict]: A list of pull request objects (as JSON dictionaries) returned
        by the GitHub API. Each dictionary contains metadata about a closed pull
        request, such as its number, title, user, state, and timestamps.
    """

    total_pages, first_page_data = await get_total_num_pages(owner, repo, base_url=base_url, github_token=github_token, per_page=per_page)

    url = base_url + f"/repos/{owner}/{repo}/pulls"
    headers = BASE_HEADERS

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
    """Filter pull requests created after a given datetime threshold.

    Args:
        prs_list (list[dict]): A list of pull request objects (as JSON dictionaries)
            returned by the GitHub API. Each dictionary must include a "created_at"
            field in ISO 8601 format (e.g., "2025-08-19T15:32:10Z").
        time_delta (datetime): A timezone-aware datetime object. Only pull requests
            created strictly after this datetime will be included in the results.

    Returns:
        tuple[list[int], list[dict]]: A tuple where:
            - The first element is a list of pull request numbers (ints) that
              satisfy the time filter.
            - The second element is the raw list of corresponding pull request
              objects (dicts) for those numbers.
    """
        
    filtered_list = []
    raw_filtered_list = []

    for pr in prs_list:
        dt = datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        
        if dt > time_delta:
            filtered_list.append(pr["number"])
            raw_filtered_list.append(pr)

    return filtered_list, raw_filtered_list



async def _get_single_pr_async(client, owner, repo, pr_id):
    """Fetch details for a single pull request from the GitHub API.

    Args:
        client (httpx.AsyncClient): An active HTTPX async client used to perform
            the request.
        owner (str): The GitHub account or organization name that owns the repository.
        repo (str): The name of the repository containing the pull request.
        pr_id (int): The pull request number (ID) to fetch details for.

    Returns:
        tuple[int, dict | None]: A tuple where:
            - The first element is the pull request number (int).
            - The second element is the pull request data (dict) if the request
              succeeds with status code 200, otherwise None.
    """

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_id}"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return pr_id, resp.json()
    except Exception as e:
        print(f"Error fetching PR #{pr_id}: {e}")
    return pr_id, None



def _get_pr_closer(owner, repo, pr_number, base_url, github_token):
    """Fetch the username of the actor who closed a specific pull request.

    Args:
        owner (str): The GitHub account or organization name that owns the repository.
        repo (str): The name of the repository containing the pull request.
        pr_number (int): The number (ID) of the pull request to inspect.
        base_url (str): The base URL of the GitHub REST API (e.g., "https://api.github.com").
        github_token (str): Personal access token for authentication. If None,
            the request will be unauthenticated and subject to stricter rate limits.

    Returns:
        str | None: The GitHub username (login) of the actor who closed the pull request,
        or None if the request fails or no "closed" event is found.
    """

    url = base_url + f"/repos/{owner}/{repo}/issues/{pr_number}/events"
    headers = BASE_HEADERS

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
    """Aggregate information about maintainers who closed or merged pull requests.

    Args:
        owner (str): The GitHub account or organization name that owns the repository.
        repo (str): The name of the repository to analyze.
        pr_list (list[int]): A list of pull request numbers (IDs) to fetch detailed
            information for.
        base_url (str): The base URL of the GitHub REST API (e.g., "https://api.github.com").
        github_token (str): Personal access token for authentication. If None, requests
            will be unauthenticated and subject to stricter rate limits.

    Returns:
        dict[str, dict[str, int]]: A dictionary mapping each maintainer's GitHub login
        name to a nested dictionary with counts of pull requests they closed or merged.
        Example:
            {
                "alice": {"closed": 2, "merged": 5},
                "bob": {"closed": 1, "merged": 3}
            }
    """
    
    maintainers_info = {}
    headers = BASE_HEADERS

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
