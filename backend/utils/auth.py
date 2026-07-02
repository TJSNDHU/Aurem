"""Authentication utilities for the AUREM backend."""

from functools import wraps
from flask import request, jsonify
from werkzeug.exceptions import Unauthorized

def require_auth(f):
    """
    Decorator that enforces JWT authentication for protected routes.

    Validates the presence and validity of an Authorization header with a Bearer token.
    Attaches the decoded JWT payload to the request object as `request.user`.

    Returns:
        Unauthorized (401): If no token is provided or token is invalid.
        Forbidden (403): If token is valid but lacks required permissions.

    Example:
        @app.route('/protected')
        @require_auth
        def protected_route():
            user_id = request.user['userId']
            return jsonify(message=f"Hello {user_id}")
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            raise Unauthorized('Authorization header is required')

        try:
            token = auth_header.split(' ')[1]
            payload = verify_jwt(token)  # Assumes verify_jwt is implemented elsewhere
            request.user = payload
        except IndexError:
            raise Unauthorized('Invalid token format. Expected: Bearer <token>')
        except Exception as e:
            raise Unauthorized(f'Invalid token: {str(e)}')

        return f(*args, **kwargs)
    return decorated_function
