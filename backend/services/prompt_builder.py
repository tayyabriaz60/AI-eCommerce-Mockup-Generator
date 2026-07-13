"""
Builds the text prompt sent to Gemini based on the user's selections.

Kept isolated from gemini_service.py so prompt wording can be iterated on
independently of the API call plumbing.
"""

STYLE_DESCRIPTIONS = {
    "White Background": "a clean, pure white studio background with soft, even lighting",
    "Studio Lighting": "a professional photography studio setup with dramatic, well-controlled lighting and subtle shadows",
    "Lifestyle Scene": "a natural, real-world lifestyle setting where the product is used or displayed in context (e.g. a home, cafe, or outdoor scene)",
    "Flat Lay": "a top-down flat lay arrangement on a styled surface with complementary props",
    "Minimalist": "a minimalist scene with lots of negative space, muted neutral tones, and simple composition",
}

PLATFORM_NOTES = {
    "Etsy": "a handmade/artisanal marketplace listing photo, warm and inviting",
    "Shopify": "a polished branded storefront product photo",
    "Amazon": "a bright, clear, detail-oriented marketplace listing photo",
    "TikTok Shop": "an eye-catching, social-media-native product photo that feels authentic and scroll-stopping",
    "Custom": "a general-purpose eCommerce product photo",
}


def build_prompt(platform: str, style: str, product_type: str) -> str:
    """Build the Gemini prompt for a given platform / style / product type combo."""
    style_desc = STYLE_DESCRIPTIONS.get(style, style)
    platform_desc = PLATFORM_NOTES.get(platform, platform)

    return (
        "Generate a realistic, high-quality product mockup. "
        f"Product type: {product_type}. "
        f"Show this exact design/image applied realistically onto the {product_type.lower()}, "
        f"photographed in {style_desc}, suitable for {platform_desc} on {platform}. "
        "Maintain accurate lighting, shadows, correct proportions and perspective, and preserve the "
        "original design's colors and details exactly as uploaded — do not distort or alter the design itself. "
        "The output should look like a professional eCommerce product photo, sharp and high resolution."
    )
