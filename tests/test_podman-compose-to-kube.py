import pytest
import unittest.mock as mock
import argparse
import os
import shutil

from podman_compose_to_kube import *


@pytest.mark.parametrize(
    "pod_name, expected_result",
    [
        ("pod_counter", "counter"),
        ("pod-counter", "counter"),
        ("podcounter", "counter"),
    ],
    ids=["pod1", "pod2", "pod3"],
)
def test_set_kube_name(pod_name, expected_result):
    argparse.Namespace.pod_name = pod_name
    kube_name = set_kube_name(argparse.Namespace)
    assert kube_name == expected_result


@pytest.mark.parametrize(
    "yaml_section, expected_result",
    [
        ("simplename", "simplename"),
        (123, 123),
        ({"name": "simplename"}, {"name": "simplename"}),
        ({"name": "simple-name"}, {"name": "simple-name"}),
        ({"name": "simple_name"}, {"name": "simple-name"}),
        (
            {"section1": {"name": "simple_name"}, "section2": {"name": "simple_name"}},
            {"section1": {"name": "simple-name"}, "section2": {"name": "simple-name"}},
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
    ],
    ids=[
        "base_case1",
        "base_case2",
        "simple_dict",
        "replace_not_needed",
        "replace_needed",
        "several_sections",
        "multiple_levels_of_nesting",
    ],
)
def test_replace_underscores_in_names_elements(yaml_section, expected_result):
    assert replace_underscores_in_names_elements(yaml_section) == expected_result


@pytest.mark.parametrize(
    "yaml_section, expected_result",
    [
        ({"0": {"services": {}}}, []),
        ({"0": {"services": {"service1": 0, "service2": 1}}}, ["service1", "service2"]),
        (
            {
                "0": {"services": {"service0": 0, "service1": 1}},
                "1": {"services": {"service2": 0, "service3": 1}},
            },
            ["service0", "service1", "service2", "service3"],
        ),
    ],
    ids=["empty_rez", "simple_rez", "several_sections"],
)
def test_get_services_names(yaml_section, expected_result):
    assert get_services_names(yaml_section) == expected_result


@pytest.mark.parametrize(
    "compose_section, service, expected_result",
    [
        ({"services": {"service": {"k": "v"}}}, "service", []),
        (
            {"services": {"service": {"environment": {"n": "v"}}}},
            "service",
            [{"name": "n", "value": "v"}],
        ),
        (
            {"services": {"service": {"environment": {"n0": "v0", "n1": "v1"}}}},
            "service",
            [{"name": "n0", "value": "v0"}, {"name": "n1", "value": "v1"}],
        ),
        (
            {
                "services": {
                    "service": {"environment": {"n": "v"}},
                    "other_service": {"environment": {"n": "v"}},
                }
            },
            "service",
            [{"name": "n", "value": "v"}],
        ),
    ],
    ids=["empty_env", "one_value", "several_values", "several_services"],
)
def test_get_environment_from_service(compose_section, service, expected_result):
    assert get_environment_from_service(compose_section, service) == expected_result


@pytest.mark.parametrize(
    "yaml_section, expected_result",
    [
        ({"spec": {"volumes": []}}, []),
        (
            {
                "spec": {
                    "volumes": [{"persistentVolumeClaim": {"claimName": "volume_name"}}]
                }
            },
            ["volume_name"],
        ),
        (
            {
                "spec": {
                    "volumes": [
                        {"persistentVolumeClaim": {"claimName": "volume_name0"}},
                        {"persistentVolumeClaim": {"claimName": "volume_name1"}},
                    ],
                }
            },
            ["volume_name0", "volume_name1"],
        ),
    ],
    ids=["empty_volume_name", "one_volume_name", "several_volume_names"],
)
def test_get_volume_names(yaml_section, expected_result):
    assert get_volume_names(yaml_section) == expected_result


@pytest.mark.parametrize(
    "service_file, environment, expected_result",
    [
        (
            {"spec": {"containers": []}},
            [{"name": "n", "value": "v"}, {"name": "n", "value": "v"}],
            {"spec": {"containers": []}},
        ),
        (
            {"spec": {"containers": [{"env": []}]}},
            [],
            {"spec": {"containers": [{"env": []}]}},
        ),
        (
            {"spec": {"containers": [{"env": []}]}},
            [{"name": "n", "value": "v"}, {"name": "n", "value": "v"}],
            {
                "spec": {
                    "containers": [
                        {
                            "env": [
                                {"name": "n", "value": "v"},
                                {"name": "n", "value": "v"},
                            ]
                        }
                    ]
                }
            },
        ),
        (
            {"spec": {"containers": [{"env": []}, {"env": []}]}},
            [{"name": "n", "value": "v"}, {"name": "n", "value": "v"}],
            {
                "spec": {
                    "containers": [
                        {
                            "env": [
                                {"name": "n", "value": "v"},
                                {"name": "n", "value": "v"},
                            ]
                        },
                        {
                            "env": [
                                {"name": "n", "value": "v"},
                                {"name": "n", "value": "v"},
                            ]
                        },
                    ]
                }
            },
        ),
        (
            {
                "spec": {
                    "containers": [
                        {
                            "env": [
                                {"k": "v"},
                            ]
                        },
                    ]
                }
            },
            [{"name": "n", "value": "v"}, {"name": "n", "value": "v"}],
            {
                "spec": {
                    "containers": [
                        {
                            "env": [
                                {"name": "n", "value": "v"},
                                {"name": "n", "value": "v"},
                            ]
                        },
                    ]
                }
            },
        ),
    ],
    ids=["dont_set_env", "empty_environment", "one_env", "several_env", "set_new_env"],
)
def test_set_environment(service_file, environment, expected_result):
    assert set_environment(service_file, environment) == expected_result


@pytest.mark.parametrize(
    "compose_file, service, expected_result",
    [
        ({"services": {"service": {"ports": []}}}, "service", None),
        (
            {
                "services": {
                    "service": {
                        "ports": [{"name": "80", "port": "80", "targetPort": 80}]
                    }
                }
            },
            "service",
            [{"name": "80", "port": "80", "targetPort": 80}],
        ),
        (
            {
                "services": {
                    "service": {
                        "ports": [{"name": "80", "port": "80", "targetPort": 80}]
                    },
                    "other_service": {
                        "ports": [{"name": "81", "port": "81", "targetPort": 81}]
                    },
                }
            },
            "service",
            [{"name": "80", "port": "80", "targetPort": 80}],
        ),
    ],
    ids=["empty_ports", "simple", "several_services"],
)
def test_get_ports(compose_file, service, expected_result):
    argparse.Namespace.verbose = False
    assert get_ports(compose_file, service, argparse.Namespace) == expected_result


def comparison_dirs(input_dir, output_dir):
    input_content = os.listdir(input_dir)
    output_content = os.listdir(output_dir)
    assert input_content == output_content
    for ic in input_content:
        if os.path.isdir(f"{input_dir}/{ic}"):
            comparison_dirs(f"{input_dir}/{ic}", f"{output_dir}/{ic}")
        elif os.path.isfile(f"{input_dir}/{ic}"):
            input_file = read_file(f"{input_dir}/{ic}")
            output_file = read_file(f"{output_dir}/{ic}")
            assert input_file == output_file


@mock.patch("podman_compose_to_kube.podman_kube_generate")
@mock.patch("podman_compose_to_kube.generate_a_k8s_service_file")
@mock.patch("podman_compose_to_kube.parse_args")
@pytest.mark.parametrize(
    "t", [("pod"), ("deployment")], ids=["type_pod", "type_deploy"]
)
def test_main(
    mock_parse_args, mock_generate_a_k8s_service_file, mock_podman_kube_generate, t
):
    try:
        os.mkdir(os.path.join(os.getcwd(), "tests/output"))
    except FileExistsError:
        pass
    try:
        os.mkdir(os.path.join(os.getcwd(), "tests/output/mnt"))
    except FileExistsError:
        pass
    mock_args = mock.Mock()
    mock_args.type = t
    mock_args.namespace = "default"
    mock_args.dir = "./tests/output/manifests"
    mock_args.pvpath = "./tests/output/mnt/PersistentVolumes"
    mock_args.user = ""
    mock_args.group = ""
    mock_args.output = "yml"
    mock_args.verbose = False
    mock_args.pod_name = "pod_counter"
    mock_args.docker_compose_file_name = "./tests/input/docker-compose.yml"
    mock_parse_args.return_value = mock_args
    mock_generate_a_k8s_service_file.return_value = read_file(
        "./tests/input/podService.yml"
    )
    mock_podman_kube_generate.return_value = read_file("./tests/input/volume.yml")
    main()
    shutil.rmtree("./tests/output/mnt")
    comparison_dirs(f"{os.getcwd()}/tests/{t}", f"{os.getcwd()}/tests/output")
    shutil.rmtree("./tests/output")
