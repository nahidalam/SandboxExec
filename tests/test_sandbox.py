from sandbox import Sandbox


def test_agent_a_executes_python_inside_docker():
    sandbox = Sandbox(name="agent_a", workdir="/tmp/sandboxexec-test")
    result = sandbox.run_python("print('hello from docker')")
    assert result["exit_code"] == 0
    assert "hello from docker" in result["stdout"]
    assert result["cleanup_done"] is True
