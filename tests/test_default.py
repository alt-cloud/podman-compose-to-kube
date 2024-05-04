import pytest
import argparse

from podman_compose_to_kube import *


class TestDefault:
    @pytest.mark.parametrize(
        "yaml_section, expected_result",
        [
            ("simplename", "simplename"),
            (123, 123),
            ({"name": "simplename"}, {"name": "simplename"}),
            ({"name": "simple-name"}, {"name": "simple-name"}),
            ({"name": "simple_name"}, {"name": "simple-name"}),
            (
                {
                    "section1": {"name": "simple_name"},
                    "section2": {"name": "simple_name"},
                },
                {
                    "section1": {"name": "simple-name"},
                    "section2": {"name": "simple-name"},
                },
            ),
            (
                {
                    "section1": {"name": "simple_name"},
                    "other_section": [
                        {"name": "somename", "k": "v"},
                        {"name": "some-name", "k": "v"},
                        {"name": "some_name", "k": "v"},
                    ],
                },
                {
                    "section1": {"name": "simple-name"},
                    "other_section": [
                        {"name": "somename", "k": "v"},
                        {"name": "some-name", "k": "v"},
                        {"name": "some-name", "k": "v"},
                    ],
                },
            ),
            (
                {"env": [{"name": "simple-name"}, {"name": "simple_name"}]},
                {"env": [{"name": "simple-name"}, {"name": "simple_name"}]},
            ),
        ],
        ids=[
            "base_case1",
            "base_case2",
            "simple_dict",
            "replace_not_needed",
            "replace_needed",
            "several_sections",
            "multiple_levels_of_nesting",
            "dont_touch_env",
        ],
    )
    def test_replace_underscores_in_names_elements(self, yaml_section, expected_result):
        assert (
            Default.replace_underscores_in_names_elements(yaml_section)
            == expected_result
        )

    @pytest.mark.parametrize(
        "pod_name, expected_result",
        [
            ("pod_counter", "counter"),
            ("pod-counter", "counter"),
            ("podcounter", "counter"),
        ],
        ids=["pod1", "pod2", "pod3"],
    )
    def test_set_kube_name(self, pod_name, expected_result):
        argparse.Namespace.pod_name = pod_name
        Default.set_kube_name(Default, argparse.Namespace)
        assert Default.kube_name == expected_result

    @pytest.mark.parametrize(
        "docker_compose_file_path",
        [("tests/input/docker-compose.yml")],
        ids=["docker_compose_1"],
    )
    def test_set_docker_compose_file(self, docker_compose_file_path):
        argparse.Namespace.docker_compose_file_name = docker_compose_file_path
        docker_compose_content = File.read(Path(docker_compose_file_path))
        docker_compose_content = Default.parse_yaml(docker_compose_content)
        Default.set_docker_compose_file(Default, argparse.Namespace)
        assert Default.docker_compose_file == docker_compose_content

    @pytest.mark.parametrize(
        "docker_compose_file_path, expected_result",
        [("tests/input/docker-compose.yml", ["redis", "web"])],
        ids=["docker_compose_1"],
    )
    def test_set_services(self, docker_compose_file_path, expected_result):
        argparse.Namespace.docker_compose_file_name = docker_compose_file_path
        Default.set_docker_compose_file(Default, argparse.Namespace)
        Default.set_services(Default)
        assert Default.services == expected_result

    @pytest.mark.parametrize(
        "docker_compose_file_path, expected_result",
        [
            (
                "tests/input/docker-compose.yml",
                {
                    "redis": [],
                    "web": [
                        {"name": "REDIS_HOST", "value": "redis"},
                        {"name": "REDIS_PORT", "value": "6379"},
                    ],
                },
            )
        ],
        ids=["docker_compose_1"],
    )
    def test_set_environments(self, docker_compose_file_path, expected_result):
        argparse.Namespace.docker_compose_file_name = docker_compose_file_path
        Default.set_docker_compose_file(Default, argparse.Namespace)
        Default.set_services(Default)
        Default.set_environments(Default)
        assert Default.environments == expected_result

    @pytest.mark.parametrize(
        "docker_compose_file_path, expected_result",
        [("tests/input/docker-compose.yml", {"redis": [6379], "web": ["8080:8080"]})],
        ids=["docker_compose_1"],
    )
    def test_set_ports(self, docker_compose_file_path, expected_result):
        argparse.Namespace.docker_compose_file_name = docker_compose_file_path
        Default.set_docker_compose_file(Default, argparse.Namespace)
        Default.set_services(Default)
        Default.set_ports(Default)
        assert Default.ports == expected_result

    @pytest.mark.parametrize(
        "docker_compose_file_path, expected_hosts, expected_tags",
        [
            (
                "tests/input/docker-compose.yml",
                {"redis": "docker.io/redis", "web": "localhost/hello-py-aioweb"},
                {"redis": "alpine", "web": "latest"},
            )
        ],
        ids=["docker_compose_1"],
    )
    def test_set_repositories_and_tags(
        self, docker_compose_file_path, expected_hosts, expected_tags
    ):
        argparse.Namespace.docker_compose_file_name = docker_compose_file_path
        Default.set_docker_compose_file(Default, argparse.Namespace)
        Default.set_services(Default)
        Default.set_repositories_and_tags(Default)
        assert Default.repositories == expected_hosts
        assert Default.tags == expected_tags