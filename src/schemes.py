"""The schemes in scope (v1: Groww Mutual Fund only).

Each scheme has a short key used in metadata, its official name, the names it
appears under inside AMC documents, and everyday aliases users might type.
"""

AMC = "Groww Mutual Fund"

SCHEMES = {
    "large_cap": {
        "name": "Groww Large Cap Fund",
        "doc_names": ["Groww Large Cap Fund", "Groww Largecap Fund", "GROWW Large Cap Fund"],
        "aliases": ["large cap", "largecap", "large-cap", "bluechip", "blue chip"],
    },
    "elss": {
        "name": "Groww ELSS Tax Saver Fund",
        "doc_names": ["Groww ELSS Tax Saver Fund", "GROWW ELSS Tax Saver Fund"],
        "aliases": ["elss", "tax saver", "tax saving", "tax-saver", "80c"],
    },
    "multicap": {
        "name": "Groww Multicap Fund",
        "doc_names": ["Groww Multicap Fund", "GROWW Multicap Fund"],
        "aliases": ["multicap", "multi cap", "multi-cap"],
    },
    "liquid": {
        "name": "Groww Liquid Fund",
        "doc_names": ["Groww Liquid Fund", "GROWW Liquid Fund"],
        "aliases": ["liquid"],
    },
}


def scheme_name(key: str) -> str:
    """Official name for a scheme key, or a generic label for AMC-wide content."""
    return SCHEMES[key]["name"] if key in SCHEMES else AMC
