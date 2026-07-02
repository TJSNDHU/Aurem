"""Authentication utilities for the AUREM backend."""

import os
from functools import wraps
from flask import request
from werkzeug.exceptions import Unauthorized, Forbidden

try:
    import jwt as pyjwt
except ImportError:  # pragma: no cover
    pyjwt = None


def verify_jwt(token):
    """
    Verify and decode a JWT token.

    Uses the ``JWT_SECRET`` environment variable as the signing key and the
    ``HS256`` algorithm by default. The algorithm can be overridden via the
    ``JWT_ALGORITHM`` environment variable.

    Parameters:
        token (str): The JWT token string to verify.

    Returns:
        dict: The decoded JWT payload.

    Raises:
        Unauthorized: If the token is invalid, expired, or cannot be decoded.
    """
    if pyjwt is None:
        raise Unauthorized('PyJWT is not installed')

    secret = os.environ.get('JWT_SECRET', 'dev-secret')
    algorithm = os.environ.get('JWT_ALGORITHM', 'HS256')

    try:
        payload = pyjwt.decode(token, secret, algorithms=[algorithm])
    except pyjwt.ExpiredSignatureError:
        raise Unauthorized('Token has expired')
    except pyjwt.InvalidTokenError as e:
        raise Unauthorized(f'Invalid token: {str(e)}')

    return payload


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
            payload = verify_jwt(token)
            request.user = payload
        except IndexError:
            raise Unauthorized('Invalid token format. Expected: Bearer <token>')
        except Exception as e:
            raise Unauthorized(f'Invalid token: {str(e)}')

        return f(*args, **kwargs)
    return decorated_function

def require_admin(f):
    """
    Decorator that enforces admin-level access for protected routes.

    Wraps `require_auth` to first validate the JWT, then checks the decoded
    payload to ensure the authenticated user has the `admin` role. The
    decoded JWT payload is available on `request.user`.

    Parameters:
        f (callable): The view function to wrap.

    Returns:
        callable: The wrapped view function.

    Raises:
        Unauthorized: If no token is provided or the token is invalid.
        Forbidden: If the token is valid but the user does not have the
            `admin` role.

    Example:
        @app.route('/admin/users')
        @require_admin
        def list_users():
            return jsonify(users=get_all_users())
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            raise Unauthorized('Authorization header is required')

        try:
            token = auth_header.split(' ')[1]
            payload = verify_jwt(token)
            request.user = payload
        except IndexError:
            raise Unauthorized('Invalid token format. Expected: Bearer <token>')
        except Exception as e:
            raise Unauthorized(f'Invalid token: {str(e)}')

        if payload.get('role') != 'admin':
            raise Forbidden('Admin privileges are required')

        return f(*args, **kwargs)
    return decorated_function