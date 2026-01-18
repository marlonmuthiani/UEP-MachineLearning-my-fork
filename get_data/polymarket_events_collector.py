from typing import List, Dict, Any, Optional

import requests

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"


class GammaAPIClient:
    def __init__(self, base_url: str = GAMMA_BASE_URL, timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.timeout = timeout

    def get_events(
        self,
        limit: int = 100,
        offset: int = 0,
        active: Optional[bool] = None,
        closed: Optional[bool] = None,
        archived: Optional[bool] = None,
        order: str = "id",
        ascending: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Pobiera listę eventów wraz z ich marketami.

        Zgodnie z docs, do pobierania wszystkich aktywnych rynków:
        GET /events?order=id&ascending=false&closed=false&limit=100[web:12]
        """
        url = f"{self.base_url}/events"
        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "order": order,
            "ascending": str(ascending).lower(),
        }
        if active is not None:
            params["active"] = str(active).lower()
        if closed is not None:
            params["closed"] = str(closed).lower()
        if archived is not None:
            params["archived"] = str(archived).lower()

        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError("Expected list from /events")
        return data