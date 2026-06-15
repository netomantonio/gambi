import json

from gambi.config import Settings, load_agents_file, parse_agents


def test_parse_agents_env_string_uses_default_knowledge():
    entries = parse_agents("stackspot-dev=01ABC, arch=01XYZ", default_knowledge=False)
    assert [e.model_id for e in entries] == ["stackspot-dev", "arch"]
    assert entries[0].agent_id == "01ABC"
    assert entries[0].options.stackspot_knowledge is False  # herdou o default
    # flags por agent não existem no atalho env → ficam no default
    assert entries[0].options.deep_search_ks is False


def test_parse_agents_ignores_malformed_pairs():
    entries = parse_agents("ok=1,, semigual, =semmodelo, m=", default_knowledge=True)
    assert [e.model_id for e in entries] == ["ok"]


def test_load_agents_file_reads_per_agent_options(tmp_path):
    path = tmp_path / "gambi.agents.json"
    path.write_text(
        json.dumps(
            [
                {
                    "model_id": "stackspot-dev",
                    "agent_id": "01ABC",
                    "stackspot_knowledge": False,
                    "deep_search_ks": True,
                    "return_ks_in_response": True,
                    "knowledge_source_ids": ["ks-1"],
                    "agent_version_number": 2,
                },
                {"model_id": "minimo", "agent_id": "01DEF"},  # só o obrigatório
            ]
        ),
        encoding="utf-8",
    )
    entries = load_agents_file(path, default_knowledge=True)

    dev = entries[0]
    assert dev.agent_id == "01ABC"
    assert dev.options.stackspot_knowledge is False
    assert dev.options.deep_search_ks is True
    assert dev.options.knowledge_source_ids == ("ks-1",)
    assert dev.options.agent_version_number == 2

    minimo = entries[1]
    assert minimo.options.stackspot_knowledge is True  # herdou default
    assert minimo.options.agent_version_number is None


def test_settings_from_env_prefers_file_over_env_string(tmp_path):
    path = tmp_path / "agents.json"
    path.write_text(json.dumps([{"model_id": "a", "agent_id": "01"}]), encoding="utf-8")
    settings = Settings.from_env(
        {
            "GAMBI_STACKSPOT_REALM": "minha-conta",
            "GAMBI_AGENTS_FILE": str(path),
            "GAMBI_AGENTS": "ignorado=99",  # deve ser ignorado quando o arquivo existe
        }
    )
    assert [e.model_id for e in settings.agents] == ["a"]
    assert settings.realm == "minha-conta"
