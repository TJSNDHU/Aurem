# HumanEval/162
# Loki Mode Multi-Agent Solution
# Attempts: 1
# Passed: True

def string_to_md5(text):
    """
    Given a string 'text', return its sha256 hash equivalent string.
    If 'text' is an empty string, return None.

    >>> string_to_md5('Hello world') == 'c0535e4be2b79ffd93291305436bf889314e4a3faec05ecffcbb7df31ad9e51a'
    """
    if text == '':
        return None
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()