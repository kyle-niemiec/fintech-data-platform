from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_ssm_release_deploy_starts_instance_before_ssm_deploy_command() -> None:
    script = _read("infra/ops/ssm_release_deploy.sh")

    assert "\nstart_instance_for_deploy\n" in script
    assert "deploy_command_id=\"$(send_deploy_command \"$TAG\")\"" in script
    assert script.index("\nstart_instance_for_deploy\n") < script.index(
        "deploy_command_id=\"$(send_deploy_command \"$TAG\")\""
    )


def test_ssm_release_deploy_always_stops_instance_via_exit_trap() -> None:
    script = _read("infra/ops/ssm_release_deploy.sh")

    assert "trap cleanup_on_exit EXIT" in script
    assert "if ! stop_instance_after_deploy; then" in script
    assert "aws_cmd ec2 stop-instances --instance-ids \"$INSTANCE_ID\" >/dev/null" in script
    assert "aws_cmd ec2 wait instance-stopped --instance-ids \"$INSTANCE_ID\"" in script
