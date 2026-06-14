# agents/app/tools.py
"""Framework-agnostic tool builders. Each tool is a plain async callable closing
over the backend client + the request's interim key. The framework adapter
(llm_agent.py) wraps these with the agent_framework `tool` decorator; keeping
them undecorated here means they (and their tests) never import the framework."""
from typing import Optional


def build_tools(backend, key: str) -> list:
    """Build the six statistics tools bound to this request's interim key."""

    async def get_statistics_summary(
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        product: Optional[str] = None,
    ) -> dict:
        """Get aggregate article counts for a period: total, awaiting_review,
        in_review, approved, rejected, auto_approved. date_from/date_to are 'YYYY-MM-DD'
        (Asia/Ho_Chi_Minh); product is an optional product code like 'CL'."""
        return await backend.get_summary(key, from_=date_from, to=date_to, product=product)

    async def get_qc_breakdown(
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        product: Optional[str] = None,
    ) -> dict:
        """Per-QC breakdown for a period: each QC's products, articles claimed,
        approved, rejected, and claimed-but-auto-approved. Same date/product args
        as the summary tool."""
        return await backend.get_qc_breakdown(key, from_=date_from, to=date_to, product=product)

    async def list_creators(
        query: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        product: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """List creators (paginated). 'query' filters by email substring. When a
        date range is given, restricts to creators with >=1 article in it; each
        item includes article_count_in_window."""
        return await backend.list_creators(
            key, q=query, from_=date_from, to=date_to, product=product, page=page, limit=limit
        )

    async def list_creator_articles(
        creator_id: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        product: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """List a single creator's articles in a period (paginated): each article's
        status, product, on_air_date, claiming QC, and reviewer. 'creator_id' is the
        creator's user id (e.g. from list_creators)."""
        return await backend.list_creator_articles(
            key, creator_id=creator_id, from_=date_from, to=date_to, product=product, page=page, limit=limit
        )

    async def list_all_articles(
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        product: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """List ALL submitted articles in a period (paginated). Each item has the
        article's name, product, status, on_air_date, and the resolved emails of
        its creator, the QC who claimed it, and its reviewer. Use for the master
        article overview across all creators."""
        return await backend.list_all_articles(
            key, from_=date_from, to=date_to, product=product, page=page, limit=limit
        )

    async def list_qc_articles(
        qc_id: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        product: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """List the articles a single QC claimed in a period (paginated). Each item
        carries an 'outcome' of approved / auto_approved / rejected / in_review,
        plus product, on_air_date, and creator email. 'qc_id' comes from the
        qc_breakdown tool's qc_id field."""
        return await backend.list_qc_articles(
            key, qc_id=qc_id, from_=date_from, to=date_to, product=product, page=page, limit=limit
        )

    return [
        get_statistics_summary, get_qc_breakdown, list_creators,
        list_creator_articles, list_all_articles, list_qc_articles,
    ]
