"""TargetMind accounts: admin-issued email + password logins.

There is no self sign-up. An administrator creates an account after an access
application is approved (``python -m agent_core.server.accounts.cli``); the
user logs in with the issued password and must change it on first login.
Sessions are opaque random tokens stored hashed in the app database and sent
as an HttpOnly cookie.
"""
