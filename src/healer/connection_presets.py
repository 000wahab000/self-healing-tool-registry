"""Small provider setup hints; suggestions, not verified compatibility guarantees."""

PRESETS = {
    "github@1": {
        "name": "GitHub",
        "version": 1,
        "source": "https://docs.github.com/en/rest",
        "verified_date": "2026-10-17",
        "kind": "openapi",
        "base_url": "https://api.github.com",
        "spec_url": "https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json",
        "auth": {"type": "bearer"},
    },
    "notion@1": {
        "name": "Notion",
        "version": 1,
        "source": "https://developers.notion.com/reference/intro",
        "verified_date": "2026-10-17",
        "kind": "openapi",
        "base_url": "https://api.notion.com/v1",
        "spec_url": "https://api.notion.com/v1/openapi.json",
        "auth": {"type": "bearer"},
        "headers": {"Notion-Version": "2022-06-28"},
    },
}
