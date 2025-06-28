import pytest

from mcpbatt.client import FrameError, RpcError


def test_rpcerror_code_message():
    err = RpcError(-32602, "missing required argument: record_id")
    assert err.code == -32602
    assert "missing required argument" in err.message
    assert "-32602" in str(err)


def test_rpcerror_is_exception():
    with pytest.raises(RpcError):
        raise RpcError(0, "boom")


def test_frameerror_plain():
    err = FrameError("server closed stdout")
    assert str(err) == "server closed stdout"
