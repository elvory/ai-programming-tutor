"""Supported editor/diagnosis languages; no source execution is provided."""

LANGUAGES = {
    "python": {"label": "Python 3", "monaco_id": "python", "extension": "py"},
    "java": {"label": "Java", "monaco_id": "java", "extension": "java"},
    "c": {"label": "C", "monaco_id": "c", "extension": "c"},
    "cpp": {"label": "C++", "monaco_id": "cpp", "extension": "cpp"},
}


def validate_language(language="python"):
    """Keep old calls Python by default and reject unknown IDs without guessing."""
    if not isinstance(language, str) or language not in LANGUAGES:
        raise ValueError("不支持的编程语言；请选择 Python 3、Java、C 或 C++。")
    return language
