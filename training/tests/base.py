import socket
from unittest.mock import patch


class DisallowedHost(AssertionError):
    """Custom exception for disallowed network connections."""

    pass


class NetworkBlockerMixin:
    """
    A test mixin that blocks all network connections by default.

    It patches `socket.socket.connect` to prevent any outgoing network calls
    during tests, ensuring the application does not make unexpected external
    requests. Connections to 'localhost' and '127.0.0.1' are allowed to
    permit database connections within the test environment.
    """

    allowed_hosts = ["localhost", "127.0.0.1"]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.original_connect = socket.socket.connect

        def block_connect(sock, address):
            host, _ = address
            if host not in cls.allowed_hosts:
                raise DisallowedHost(f"Network connection to {host} is not allowed.")
            cls.original_connect(sock, address)

        cls.socket_patcher = patch("socket.socket.connect", block_connect)
        cls.socket_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.socket_patcher.stop()
        super().tearDownClass()
