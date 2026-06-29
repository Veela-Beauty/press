"""No-op license shim. Watch Tower is Press control-plane infra (our own), not a
licensed client product, so every feature is allowed and gates are pass-through."""


def is_allowed(feature=None):
    return True


def require(feature=None):
    return True


def gated(feature=None):
    def deco(fn):
        return fn
    return deco
