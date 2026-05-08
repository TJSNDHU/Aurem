# Skill: Configure SSE Authentication for ORA Scanner

## When to Use This Skill

1. When encountering issues with EventSource authentication in ORA Scanner.
2. When required to implement token-based authentication via URL query param.
3. When backend updates are necessary to accommodate new authentication methods.

## Step-by-Step Procedure

1. **Identify HTTP Header Limitation**: Recognize that EventSource cannot send HTTP headers, which may be causing authentication issues.
2. **Switch to Query Param Token Passing**: Update the ORA Scanner configuration to pass tokens as URL query parameters instead of HTTP headers.
3. **Update Backend Authentication Logic**: Modify the backend code to read the token from the query parameter instead of expecting it in an HTTP header.
4. **Test with curl and Verify Decoded Token**: Use `curl` to test the authentication flow and verify that the decoded token is correct.
5. **Update Frontend EventSource URLs**: Update the frontend EventSource URLs to include the new token as a query parameter.

## Common Pitfalls to Avoid

* Failing to update backend code to read tokens from query parameters.
* Not testing with `curl` to ensure authentication flow works correctly.
* Forgetting to update frontend EventSource URLs.

## Expected Outcome

* The ORA Scanner will authenticate correctly using the token passed as a URL query parameter.
* All 16/16 tests should pass, indicating successful implementation of SSE authentication.