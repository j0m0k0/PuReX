from purex.core import filter_prs, get_prs_async


async def fetch_and_filter_prs(owner, repo):
    all_prs = await get_prs_async(owner, repo)
    return filter_prs(all_prs)
