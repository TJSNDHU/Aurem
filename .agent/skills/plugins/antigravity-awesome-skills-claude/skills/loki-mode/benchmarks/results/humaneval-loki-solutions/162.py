# HumanEval/162
# Loki Mode Multi-Agent Solution
# Attempts: 1
# Passed: True

def string_to_sha256(text):
    """
    Given a string 'text', return its sha256 hash equivalent string.
    If 'text' is an empty string, return None.

    >>> import hashlib
    >>> string_to_sha256('Hello world') == hashlib.sha256(b'Hello world').hexdigest()
    """
    if text == '':
        return None
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()