"""Tests for YAML config loading and inheritance."""

import pytest
import yaml
from pathlib import Path

# Import from run.py — it's at savannah/run.py, need to handle the import path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from run import load_config, _deep_merge


class TestDeepMerge:
    """Test recursive dict merging."""

    def test_simple_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3}

    def test_nested_merge(self):
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 99}}
        result = _deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 99}, "b": 3}

    def test_deep_nested_merge(self):
        base = {"a": {"b": {"c": 1, "d": 2}}}
        override = {"a": {"b": {"c": 99}}}
        result = _deep_merge(base, override)
        assert result["a"]["b"]["c"] == 99
        assert result["a"]["b"]["d"] == 2

    def test_new_key_added(self):
        base = {"a": 1}
        override = {"b": 2}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_list_replaced_not_merged(self):
        base = {"a": [1, 2, 3]}
        override = {"a": [4, 5]}
        result = _deep_merge(base, override)
        assert result["a"] == [4, 5]

    def test_original_not_mutated(self):
        base = {"a": {"x": 1}}
        override = {"a": {"y": 2}}
        _deep_merge(base, override)
        assert "y" not in base["a"]

    def test_empty_override(self):
        base = {"a": 1, "b": 2}
        result = _deep_merge(base, {})
        assert result == {"a": 1, "b": 2}


class TestLoadConfig:
    """Test YAML loading with inheritance."""

    def test_load_default_config(self):
        config_path = Path(__file__).parent.parent / "config" / "default.yaml"
        config = load_config(config_path)
        assert "simulation" in config
        assert "world" in config
        assert "agents" in config
        assert "llm" in config
        assert "perturbation" in config

    def test_default_config_values(self):
        config_path = Path(__file__).parent.parent / "config" / "default.yaml"
        config = load_config(config_path)
        assert config["world"]["grid_size"] == 30
        assert config["agents"]["count"] == 12
        assert config["llm"]["provider"] == "claude_code"
        assert config["perturbation"]["enabled"] is False
        assert config["world"]["food"]["min_sources"] == 5
        assert config["world"]["food"]["max_sources"] == 20

    def test_load_experiment_with_inheritance(self):
        config_path = Path(__file__).parent.parent / "config" / "experiments" / "perturbation.yaml"
        config = load_config(config_path)
        # Should inherit from default
        assert config["world"]["grid_size"] == 30
        assert config["agents"]["count"] == 12
        # But override perturbation
        assert config["perturbation"]["enabled"] is True
        assert config["perturbation"]["rate"] == 0.05

    def test_full_pressure_config(self):
        config_path = Path(__file__).parent.parent / "config" / "experiments" / "full_pressure.yaml"
        config = load_config(config_path)
        assert config["perturbation"]["enabled"] is True
        assert config["social"]["deceptive_agents"] == 3

    def test_baseline_config_no_perturbation(self):
        config_path = Path(__file__).parent.parent / "config" / "experiments" / "baseline.yaml"
        config = load_config(config_path)
        assert config["perturbation"]["enabled"] is False
        assert config["social"]["deceptive_agents"] == 0

    def test_resumable_config(self):
        config_path = Path(__file__).parent.parent / "config" / "experiments" / "resumable_pressure.yaml"
        config = load_config(config_path)
        assert config["llm"]["session_mode"] == "resumable"
        assert config["perturbation"]["enabled"] is True

    def test_all_experiment_configs_load(self):
        """Every experiment config should load without error."""
        experiments_dir = Path(__file__).parent.parent / "config" / "experiments"
        for yaml_file in experiments_dir.glob("*.yaml"):
            config = load_config(yaml_file)
            assert "simulation" in config, f"{yaml_file.name} missing simulation key"
