import pytest
import unittest.mock as mock
import argparse
import os
import shutil

from podman_compose_to_kube import *


def comparison_dirs(input_dir, output_dir):
    input_content = os.listdir(input_dir)
    output_content = os.listdir(output_dir)
    assert input_content == output_content
    for ic in input_content:
        if os.path.isdir(f"{input_dir}/{ic}"):
            comparison_dirs(f"{input_dir}/{ic}", f"{output_dir}/{ic}")
        elif os.path.isfile(f"{input_dir}/{ic}"):
            input_file = File.read(Path(f"{input_dir}/{ic}"))
            output_file = File.read(Path(f"{output_dir}/{ic}")).replace(
                f"{os.getcwd()}/./tests/output", ""
            )
            assert input_file == output_file


class PodmanKube:
    """Contains functions for using the podman kube utility"""

    @staticmethod
    def generate(pod_name: str, is_service: bool) -> str:
        """podman kube generate"""
        service = "-service" if is_service else ""
        return File.read(Path(f"./tests/input/{pod_name}{service}.yml"))


@mock.patch("podman_compose_to_kube.Helm.create")
@mock.patch(
    "podman_compose_to_kube.PodmanKube.generate",
    side_effect=PodmanKube.generate,
)
@mock.patch("podman_compose_to_kube.ArgsParser.get_args")
@pytest.mark.parametrize(
    "t",
    [
        ("pod"),
        ("deployment"),
        ("helm"),
    ],
    ids=["type_pod", "type_deploy", "type_helm"],
)
def test_main(mock_get_args, mock_podman_kube_generate, mock_helm_create, t):
    Default.services = []
    argparse.Namespace.type = t
    argparse.Namespace.namespace = "default"
    argparse.Namespace.dir = "./tests/output/manifests"
    argparse.Namespace.pvpath = "./tests/output/mnt/PersistentVolumes"
    argparse.Namespace.user = ""
    argparse.Namespace.group = ""
    argparse.Namespace.output = "yml"
    argparse.Namespace.verbose = False
    argparse.Namespace.pod_name = "pod_counter"
    argparse.Namespace.docker_compose_file_name = "./tests/input/docker-compose.yml"
    mock_get_args.return_value = argparse.Namespace
    mock_helm_create.return_value = None
    Dir.mkdir(os.path.join(os.getcwd(), "tests/output/mnt"))
    Util()
    shutil.rmtree(os.path.join(os.getcwd(), "tests/output/mnt"))
    comparison_dirs(f"{os.getcwd()}/tests/{t}", f"{os.getcwd()}/tests/output")
    shutil.rmtree(os.path.join(os.getcwd(), "tests/output/"))