import json

from gambi.config import Settings, load_agents_file, parse_agents


def _ask(route):
    return route.by_mode["ask"]


def test_parse_agents_env_string_uses_default_knowledge():
    routes = parse_agents("stackspot-dev=01ABC, arch=01XYZ", default_knowledge=False)
    assert [r.model_id for r in routes] == ["stackspot-dev", "arch"]
    assert _ask(routes[0]).agent_id == "01ABC"
    assert _ask(routes[0]).options.stackspot_knowledge is False  # herdou o default
    assert _ask(routes[0]).options.deep_search_ks is False
    # atalho env é mode-agnostic: mesmo target em ask e agent
    assert routes[0].by_mode["ask"] is routes[0].by_mode["agent"]


def test_parse_agents_ignores_malformed_pairs():
    routes = parse_agents("ok=1,, semigual, =semmodelo, m=", default_knowledge=True)
    assert [r.model_id for r in routes] == ["ok"]


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
                    "structured_output": True,
                },
                {"model_id": "minimo", "agent_id": "01DEF"},  # só o obrigatório
            ]
        ),
        encoding="utf-8",
    )
    routes = load_agents_file(path, default_knowledge=True)

    dev = _ask(routes[0])
    assert dev.agent_id == "01ABC"
    assert dev.options.stackspot_knowledge is False
    assert dev.options.deep_search_ks is True
    assert dev.options.knowledge_source_ids == ("ks-1",)
    assert dev.options.agent_version_number == 2
    assert dev.options.structured_output is True

    minimo = _ask(routes[1])
    assert minimo.options.stackspot_knowledge is True  # herdou default
    assert minimo.options.agent_version_number is None
    assert minimo.options.structured_output is False  # default


def test_load_agents_file_alias_per_mode(tmp_path):
    path = tmp_path / "agents.json"
    path.write_text(
        json.dumps(
            [
                {
                    "model_id": "stackspot-llm-5.1",
                    "modes": {
                        "ask": {"agent_id": "01ASK", "stackspot_knowledge": True},
                        "agent": {"agent_id": "01AGENT", "structured_output": True},
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    routes = load_agents_file(path, default_knowledge=False)
    route = routes[0]
    assert route.model_id == "stackspot-llm-5.1"
    assert route.by_mode["ask"].agent_id == "01ASK"
    assert route.by_mode["ask"].options.structured_output is False
    assert route.by_mode["agent"].agent_id == "01AGENT"
    assert route.by_mode["agent"].options.structured_output is True
    # fallback: modo desconhecido cai em algum target existente
    assert route.target_for("inexistente").agent_id in {"01ASK", "01AGENT"}


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
    assert [r.model_id for r in settings.agents] == ["a"]
    assert settings.realm == "minha-conta"
