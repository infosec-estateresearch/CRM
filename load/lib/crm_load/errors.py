"""Errors carry a fixed code only, never record content."""


class LoadError(Exception):
    """A refusal or failure. ``code`` is from a fixed set; it is the only thing logged."""

    def __init__(self, code, exit_code=2):
        super().__init__(code)
        self.code = code
        self.exit_code = exit_code


class GateError(LoadError):
    def __init__(self, code):
        super().__init__(code, exit_code=3)


class TransportError(LoadError):
    def __init__(self, code, status=None):
        super().__init__(code, exit_code=4)
        self.status = status
