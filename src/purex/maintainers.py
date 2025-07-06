from purex.core import get_maintainers_info_async


async def fetch_maintainers_summary(owner, repo, pr_list):
    return await get_maintainers_info_async(owner, repo, pr_list)
