"""Test-suite compatibility shims.

starlette 0.36's ``TestClient`` forwards an ``app=`` keyword to
``httpx.Client.__init__``; httpx >= 0.28 removed that parameter (the ASGI app is
now carried solely by the ``transport=`` it also passes). Without this shim every
``TestClient``-based test errors at construction with
``Client.__init__() got an unexpected keyword argument 'app'``. We strip the dead
``app`` kwarg so the bundled starlette keeps working against the installed httpx.
"""
import httpx

_orig_client_init = httpx.Client.__init__


def _patched_client_init(self, *args, **kwargs):
    kwargs.pop("app", None)
    return _orig_client_init(self, *args, **kwargs)


httpx.Client.__init__ = _patched_client_init
