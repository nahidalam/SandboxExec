from app import run_demo


def test_full_workflow_reaches_complete():
    result = run_demo()
    assert result["status"] == "complete"
    assert result["execution"]["final_report_generated"] is True
    assert result["audit"]["timeline"][-1] == "COMPLETE"
