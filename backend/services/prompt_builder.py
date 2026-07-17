"""
Builds the text prompt sent to FLUX Kontext based on the user's selections.

Kontext expects editing-style instructions (e.g. "Place this design on a white
t-shirt, studio lighting, realistic fabric folds") rather than open-ended
generation prompts. Kept isolated from hf_flux_service.py so prompt wording
can be iterated on independently of the API call plumbing.
"""

STYLE_DESCRIPTIONS = {
    "White Background": "clean pure white studio background, soft even lighting",
    "Studio Lighting": "professional studio lighting, dramatic controlled light, subtle shadows",
    "Lifestyle Scene": "natural lifestyle setting where the product is used or displayed in context",
    "Flat Lay": "top-down flat lay on a styled surface with complementary props",
    "Minimalist": "minimalist scene with negative space, muted neutral tones, simple composition",
}

PLATFORM_NOTES = {
    "Etsy": "warm artisanal marketplace listing photo",
    "Shopify": "polished branded storefront product photo",
    "Amazon": "bright clear detail-oriented marketplace listing photo",
    "TikTok Shop": "eye-catching social-media-native product photo, authentic and scroll-stopping",
    "Custom": "general-purpose eCommerce product photo",
}

PRODUCT_SURFACE_HINTS = {
    "T-shirt": "realistic fabric folds and natural drape",
    "Mug": "realistic ceramic surface with subtle reflections",
    "Poster/Wall Art": "realistic framed wall art with correct perspective",
    "Phone Case": "realistic phone case fit with accurate proportions",
    "Tote Bag": "realistic canvas texture and natural bag shape",
    "Sticker": "realistic sticker applied to a clean surface",
    "Other": "realistic product surface with accurate proportions",
}


def build_prompt(platform: str, style: str, product_type: str) -> str:
    """Build a Kontext-style editing instruction for platform / style / product type."""
    style_desc = STYLE_DESCRIPTIONS.get(style, style)
    platform_desc = PLATFORM_NOTES.get(platform, platform)
    surface_hint = PRODUCT_SURFACE_HINTS.get(product_type, "realistic product surface")

    return (
        f"Place this exact design onto a {product_type.lower()} mockup, "
        f"{style_desc}, {surface_hint}. "
        f"Keep the uploaded design unchanged — preserve its colors, details, and proportions exactly. "
        f"Make it look like a professional {platform_desc} suitable for {platform}, "
        "with accurate lighting, shadows, and perspective. Sharp, high-resolution product photo."
    )
