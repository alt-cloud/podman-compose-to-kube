import pytest
import unittest.mock as mock
import argparse
from contextlib import nullcontext as does_not_raise

from podman_compose_to_kube import *


class TestArgsParser:
    @pytest.mark.parametrize(
        "user, group, expected_result",
        [
            ("username", "", "username"),
            ("username", "usergroup", "usergroup"),
        ],
        ids=["default_group", "not_default_group"],
    )
    def test_set_default_group(self, user, group, expected_result):
        argparse.Namespace.user = user
        argparse.Namespace.group = group
        ArgsParser.args = argparse.Namespace
        ArgsParser.set_default_group(ArgsParser)
        assert ArgsParser.args.group == expected_result

    @pytest.mark.parametrize(
        "test_type, expected_result",
        [
            ("p", "pod"),
            ("pod", "pod"),
            ("d", "deployment"),
            ("deployment", "deployment"),
            ("h", "helm"),
            ("helm", "helm"),
        ],
        ids=["p_type", "pod_type", "d_type", "deployment_type", "h_type", "helm_type"],
    )
    def test_set_type(self, test_type, expected_result):
        argparse.Namespace.type = test_type
        ArgsParser.args = argparse.Namespace
        ArgsParser.set_type(ArgsParser)
        assert ArgsParser.args.type == expected_result

    @mock.patch("podman_compose_to_kube.os.getcwd")
    @pytest.mark.parametrize(
        "path, expected_result",
        [
            ("/mnt/PersistentVolumes", "/mnt/PersistentVolumes"),
            ("PersistentVolumes", "/mnt/PersistentVolumes"),
        ],
        ids=["absolute_path", "relative_path"],
    )
    def test_set_pvpath(self, mock_getcwd, path, expected_result):
        mock_getcwd.return_value = "/mnt"
        argparse.Namespace.pvpath = path
        ArgsParser.args = argparse.Namespace
        ArgsParser.set_pvpath(ArgsParser)
        assert ArgsParser.args.pvpath == expected_result

    @pytest.mark.parametrize(
        "pod_name, expectation",
        [
            ("counter", pytest.raises(Exception)),
            ("pod_counter", does_not_raise()),
        ],
        ids=["incorrect_pod_name", "correct_pod_name"],
    )
    def test_args_check(self, pod_name, expectation):
        argparse.Namespace.pod_name = pod_name
        ArgsParser.args = argparse.Namespace
        with expectation:
            assert ArgsParser.args_check(ArgsParser) is None