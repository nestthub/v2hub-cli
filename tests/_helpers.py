"""Tests for helper functions in v2hub_cli.cli: _parse_source, _build_sources, versions."""

from __future__ import annotations

import pytest
import typer

from v2hub_cli import cli


class TestParseSource:
    def test_plain_string_source(self) -> None:
        result = cli._parse_source("vless://uuid@host:443?params#comment")
        assert result == {"data": "vless://uuid@host:443?params#comment"}

    def test_plain_string_is_stripped(self) -> None:
        result = cli._parse_source("  https://example.com/sub  ")
        assert result == {"data": "https://example.com/sub"}

    def test_json_object_minimal(self) -> None:
        result = cli._parse_source('{"data": "vless://uuid@host"}')
        assert result == {"data": "vless://uuid@host"}

    def test_json_object_with_hidden_true(self) -> None:
        result = cli._parse_source('{"data": "vless://uuid@host", "hidden": true}')
        assert result == {"data": "vless://uuid@host", "is_hidden": True}

    def test_json_object_with_hidden_false_is_omitted(self) -> None:
        # hidden defaults to false and the code only sets is_hidden when truthy
        result = cli._parse_source('{"data": "vless://uuid@host", "hidden": false}')
        assert result == {"data": "vless://uuid@host"}
        assert "is_hidden" not in result

    def test_json_object_with_depth(self) -> None:
        result = cli._parse_source('{"data": "vless://uuid@host", "depth": 2}')
        assert result == {"data": "vless://uuid@host", "max_depth": 2}

    def test_json_object_with_depth_none_is_omitted(self) -> None:
        result = cli._parse_source('{"data": "vless://uuid@host", "depth": null}')
        assert result == {"data": "vless://uuid@host"}
        assert "max_depth" not in result

    def test_json_object_with_depth_zero_is_kept(self) -> None:
        # depth=0 is falsy-adjacent but explicitly checked with "is not None"
        result = cli._parse_source('{"data": "vless://uuid@host", "depth": 0}')
        assert result == {"data": "vless://uuid@host", "max_depth": 0}

    def test_json_object_with_all_fields(self) -> None:
        result = cli._parse_source('{"data": "vless://uuid@host", "hidden": true, "depth": 3}')
        assert result == {
            "data": "vless://uuid@host",
            "is_hidden": True,
            "max_depth": 3,
        }

    def test_invalid_json_raises_bad_parameter(self) -> None:
        with pytest.raises(typer.BadParameter, match="failed to parse"):
            cli._parse_source('{"data": "unterminated')

    def test_json_missing_data_field_raises_bad_parameter(self) -> None:
        with pytest.raises(typer.BadParameter, match='must be an object with a "data" field'):
            cli._parse_source('{"hidden": true}')

    def test_json_array_raises_bad_parameter(self) -> None:
        # valid JSON, but not an object -> should be rejected
        with pytest.raises(typer.BadParameter, match='must be an object with a "data" field'):
            cli._parse_source('["not", "an", "object"]')

    def test_whitespace_before_brace_still_detected_as_json(self) -> None:
        result = cli._parse_source('   {"data": "vless://uuid@host"}  ')
        assert result == {"data": "vless://uuid@host"}

    def test_url_like_string_not_mistaken_for_json(self) -> None:
        # Must not start with "{" after stripping, so it's treated as plain data
        result = cli._parse_source("https://example.com/sub?x={y}")
        assert result == {"data": "https://example.com/sub?x={y}"}


class TestBuildSources:
    def test_empty_list(self, fake_source_create: type) -> None:
        result = cli._build_sources([])
        assert result == []

    def test_builds_source_create_objects(self, fake_source_create: type) -> None:
        result = cli._build_sources(["vless://a", "vless://b"])
        assert len(result) == 2
        assert all(isinstance(s, fake_source_create) for s in result)
        assert result[0].data == "vless://a"
        assert result[1].data == "vless://b"

    def test_mixes_plain_and_json_sources(self, fake_source_create: type) -> None:
        result = cli._build_sources(
            [
                "vless://plain",
                '{"data": "vless://json", "hidden": true, "depth": 1}',
            ]
        )
        assert len(result) == 2
        assert result[0].data == "vless://plain"
        assert result[0].is_hidden is False
        assert result[1].data == "vless://json"
        assert result[1].is_hidden is True
        assert result[1].max_depth == 1

    def test_invalid_json_source_propagates_bad_parameter(self) -> None:
        with pytest.raises(typer.BadParameter):
            cli._build_sources(["{invalid json"])


class TestPackageVersion:
    def test_installed_package_returns_version_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(cli, "version", lambda _: "1.2.3")
        assert cli._package_version("some-package") == "1.2.3"

    def test_missing_package_returns_not_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from importlib.metadata import PackageNotFoundError

        def raise_not_found(pkg: str) -> str:
            raise PackageNotFoundError(pkg)

        monkeypatch.setattr(cli, "version", raise_not_found)
        assert cli._package_version("missing-package") == "not installed"


class TestGetVersions:
    def test_returns_all_three_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cli, "_package_version", lambda pkg: f"{pkg}-version")
        versions = cli._get_versions()
        assert set(versions.keys()) == {"v2hub", "v2hub-cli", "v2hub-admin"}
        assert versions["v2hub"] == "v2hub-version"
        assert versions["v2hub-admin"] == "v2hub-admin-version"
