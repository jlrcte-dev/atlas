class RSSReaderClient:
    def fetch_items(self) -> list[dict]:
        return [
            {"title": "Mercado abre em alta", "category": "economia"},
            {"title": "Nova atualização em IA corporativa", "category": "tecnologia"},
        ]
