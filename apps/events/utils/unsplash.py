import os

import requests

UNSPLASH_RANDOM_PHOTO_URL = "https://api.unsplash.com/photos/random"

CATEGORY_KEYWORDS = {
    "concerts-and-nightlife": "live music concert night venue",
    "outdoors-and-active": "kenya hiking trail outdoor nature",
    "food-and-drink": "food market restaurant east africa",
    "culture-and-arts": "art gallery exhibition africa",
    "talks-and-ideas": "conference panel lecture auditorium",
    "workshops-and-classes": "workshop creative class studio",
    "markets-and-popups": "outdoor market stalls craft fair",
    "travel": "kenya coast beach mombasa nairobi",
}

FALLBACK_IMAGE_URLS = {
    "concerts-and-nightlife": "https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3",
    "outdoors-and-active": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4",
    "food-and-drink": "https://images.unsplash.com/photo-1504674900247-0877df9cc836",
    "culture-and-arts": "https://images.unsplash.com/photo-1531243269054-5ebf6f34081e",
    "talks-and-ideas": "https://images.unsplash.com/photo-1475721027785-f74eccf877e2",
    "workshops-and-classes": "https://images.unsplash.com/photo-1452860606245-08befc0ff44b",
    "markets-and-popups": "https://images.unsplash.com/photo-1488459716781-31db52582fe9",
    "travel": "https://images.unsplash.com/photo-1489392191049-fc10c97e64b6",
}


def _fallback_image_url(category_slug: str, index: int | None = None) -> str:
    fallback = FALLBACK_IMAGE_URLS.get(category_slug, FALLBACK_IMAGE_URLS["travel"])
    suffix = f"?v={index}" if index is not None else ""
    return f"{fallback}{suffix}"


def _fetch_random_regular_url(category_slug: str) -> str | None:
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not access_key:
        return None

    try:
        response = requests.get(
            UNSPLASH_RANDOM_PHOTO_URL,
            headers={"Authorization": f"Client-ID {access_key}"},
            params={
                "query": CATEGORY_KEYWORDS.get(category_slug, category_slug),
                "orientation": "landscape",
                "content_filter": "high",
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get("urls", {}).get("regular")
    except Exception:
        return None


def fetch_unsplash_image_url(category_slug: str) -> str | None:
    return _fetch_random_regular_url(category_slug) or _fallback_image_url(category_slug)


def fetch_unsplash_gallery_images(category_slug: str, count: int = 3) -> list[str]:
    images = []
    for index in range(1, count + 1):
        images.append(_fetch_random_regular_url(category_slug) or _fallback_image_url(category_slug, index))
    return images
