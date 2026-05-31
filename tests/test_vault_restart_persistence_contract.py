from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _service_block(yaml_text: str, service_name: str, next_service_name: str) -> str:
    start_marker = f"  {service_name}:\n"
    end_marker = f"\n  {next_service_name}:\n"
    start = yaml_text.index(start_marker)
    end = yaml_text.index(end_marker, start)
    return yaml_text[start:end]


def test_compose_declares_vault_data_volume() -> None:
    compose_root = _read("infra/docker-compose.yaml")
    assert "  vault_data:\n" in compose_root


def test_vault_service_uses_non_dev_persistent_startup() -> None:
    foundation = _read("infra/compose/foundation.yaml")
    vault_block = _service_block(foundation, "vault", "kes_bootstrap")

    assert "entrypoint: [\"/bin/sh\", \"/vault-start.sh\"]" in vault_block
    assert "- -config=/vault/config/vault.hcl" in vault_block
    assert "- -dev" not in vault_block
    assert "- ./kms/vault.hcl:/vault/config/vault.hcl:ro" in vault_block
    assert "- ./kms/vault-start.sh:/vault-start.sh:ro" in vault_block
    assert "- vault_data:/vault/data" in vault_block


def test_vault_startup_script_performs_init_unseal_and_reconcile() -> None:
    startup = _read("infra/kms/vault-start.sh")

    assert "vault operator init -status" in startup
    assert "vault operator init -key-shares=1 -key-threshold=1" in startup
    assert "vault operator unseal" in startup
    assert "/bootstrap-vault.sh" in startup


def test_vault_startup_wait_loop_handles_uninitialized_status_code() -> None:
    startup = _read("infra/kms/vault-start.sh")

    assert "vault status >/dev/null 2>&1 || status=\"$?\"" in startup
    assert "if [ \"${status}\" -eq 0 ] || [ \"${status}\" -eq 2 ]; then" in startup


def test_vault_startup_handles_expected_nonzero_codes_under_set_e() -> None:
    startup = _read("infra/kms/vault-start.sh")

    assert "vault operator init -status >/dev/null 2>&1 || init_status=\"$?\"" in startup
    assert "vault status >/dev/null 2>&1 || status=\"$?\"" in startup


def test_kes_bootstrap_waits_for_vault_credentials_file() -> None:
    kes_bootstrap = _read("infra/kms/bootstrap-kes.sh")

    assert "while [ ! -f \"${KES_VAULT_CREDS_FILE}\" ];" in kes_bootstrap


def test_makefile_cleans_vault_data_volume() -> None:
    makefile = _read("Makefile")

    assert "for suffix in postgres_data event_store_data minio_data redpanda_data kms_shared vault_data" in makefile


def test_foundation_uses_vault_startup_reconcile_without_legacy_service() -> None:
    foundation = _read("infra/compose/foundation.yaml")
    kes_bootstrap_block = _service_block(foundation, "kes_bootstrap", "kes")

    assert "\n  vault_bootstrap:\n" not in foundation
    assert "vault:\n        condition: service_healthy" in kes_bootstrap_block
