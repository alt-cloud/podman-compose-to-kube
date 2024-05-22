#!/usr/bin/python3

import argparse
import copy
import json
import os
from pathlib import Path
import pwd

import yaml


__version__ = "2.0.0"


class ArgsParser:
    """Contains arguments parser and methods for them"""

    def get_args(self) -> argparse.Namespace:
        """Parse arguments from CLI"""
        parser = argparse.ArgumentParser(description="Podman compose to k8s")
        parser.add_argument(
            "-t",
            "--type",
            type=str,
            choices=["pod", "p", "deployment", "d", "helm", "h"],
            default="pod",
            help="deployment type",
        )
        parser.add_argument(
            "-n",
            "--namespace",
            type=str,
            default="default",
            help="namespace"
        )
        parser.add_argument(
            "-d",
            "--dir",
            type=str,
            default="manifests",
            help="manifests directory"
        )
        parser.add_argument(
            "-p",
            "--pvpath",
            type=str,
            default="/mnt/PersistentVolumes",
            help="PersistentVolume directory",
        )
        parser.add_argument(
            "-u",
            "--user",
            type=str,
            default="",
            help="rootless user"
        )
        parser.add_argument(
            "-g",
            "--group",
            type=str,
            default="",
            help="rootless group"
        )
        parser.add_argument(
            "-o",
            "--output",
            type=str,
            choices=["yml", "json"],
            default="yml",
            help="output files format",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true"
        )
        parser.add_argument(
            "pod_name",
            type=str,
            help="pod name"
        )
        parser.add_argument(
            "docker_compose_file_name",
            type=str,
            help="docker compose file name"
        )
        return parser.parse_args()

    def set_default_group(self):
        if self.args.group == "":
            self.args.group = self.args.user

    def set_type(self):
        if self.args.type == "p":
            self.args.type = "pod"
        if self.args.type == "d":
            self.args.type = "deployment"
        if self.args.type == "h":
            self.args.type = "helm"

    def set_pvpath(self):
        if self.args.pvpath[0] != "/":
            self.args.pvpath = os.path.join(os.getcwd(), self.args.pvpath)

    def args_check(self):
        if self.args.pod_name[:3] != "pod":
            raise Exception("Incorrect POD name")

    def __init__(self) -> None:
        self.args = self.get_args()
        self.set_default_group()
        self.set_type()
        self.set_pvpath()
        self.args_check()


class File:
    """Contains functions for files"""

    @staticmethod
    def create(path: str, name: str, extension: str, content: dict) -> None:
        """Creates file with content"""
        file_path = Path(f"{path}/{name}.{extension}")
        if extension == "yml":
            yaml.Dumper.ignore_aliases = lambda *args: True
            file_content = "# Created with podman-compose-to-kube 1.0.0-alt1\n"
            file_content += "---\n"
            file_content += yaml.dump(
                content, default_flow_style=False, default_style=""
            )
            file_path.write_text(file_content)
        elif extension == "json":
            file_content = json.dumps(content, indent=2)
            file_path.write_text(file_content)

    @staticmethod
    def read(path: Path):
        try:
            return path.read_text()
        except FileNotFoundError:
            raise Exception(f'File "{path}" not found')


class Dir:
    """Contains functions for directories"""

    @staticmethod
    def mkdir(dir_path: str):
        path = Path(dir_path)
        path.mkdir(parents=True, exist_ok=True)


class PodmanKube:
    """Contains functions for using the podman kube utility"""

    @staticmethod
    def generate(pod_name: str, is_service: bool) -> str:
        """podman kube generate"""
        try:
            rez = ""
            cmd = f"podman kube generate {'--service' if is_service else ''} {pod_name}"
            output = os.popen(cmd, "r")
            for l in output:
                rez += l
            status = output.close()
            if status:
                raise Exception(f"cmd return {status}")
            return rez
        except:
            raise Exception(f'Service "{pod_name}" does not exists')


class Default:
    """This class contains default parameters and methods"""

    docker_compose_file = dict()
    environments = dict()
    hosts = dict()
    kube_name = ""
    ports = dict()
    repositories = dict()
    services = []
    tags = dict()
    k8s_service_file = dict()
    pod_file = dict()
    k8s_service_file_with_correct_names = dict()

    @staticmethod
    def parse_yaml(yaml_file: str) -> dict:
        """Parse yaml from string"""
        rez = dict()
        c = 0
        yamls = yaml.load_all(yaml_file, yaml.FullLoader)
        for y in yamls:
            rez[f"{c}"] = y
            c += 1
        return rez

    @staticmethod
    def replace_underscores_in_names_elements(yaml_section: dict) -> dict:
        """Changes the _ symbol to - in the yaml section, but dont touch env"""
        if isinstance(yaml_section, str) or isinstance(yaml_section, int):
            return yaml_section
        for k in yaml_section.keys():
            if k == "env":
                break
            yaml_param = yaml_section[k]
            if isinstance(yaml_param, list):
                for i in yaml_section[k]:
                    Default.replace_underscores_in_names_elements(i)
            if isinstance(yaml_param, dict):
                Default.replace_underscores_in_names_elements(yaml_section[k])
            if "name" in k.lower():
                yaml_section[k] = yaml_param.replace("_", "-")
        return yaml_section

    def set_kube_name(self, args: argparse.Namespace) -> str:
        if args.pod_name[:3] == "pod":
            self.kube_name = args.pod_name[3:]
            if self.kube_name[0] == "-" or self.kube_name[0] == "_":
                self.kube_name = self.kube_name[1:]

    def set_docker_compose_file(self, args: argparse.Namespace) -> None:
        docker_compose_path = Path(args.docker_compose_file_name)
        docker_compose_content = File.read(docker_compose_path)
        self.docker_compose_file = self.parse_yaml(docker_compose_content)

    def set_services(self) -> None:
        for k in self.docker_compose_file.keys():
            self.services += self.docker_compose_file[k]["services"].keys()

    def set_environments(self) -> None:
        for k in self.docker_compose_file.keys():
            for s in self.services:
                environment = []
                if "environment" in self.docker_compose_file[k]["services"][s].keys():
                    env = self.docker_compose_file[k]["services"][s]["environment"]
                    for e in env.keys():
                        environment.append({"name": e, "value": f"{env[e]}"})
                self.environments[s] = environment

    def set_ports(self) -> None:
        for s in self.services:
            for k in self.docker_compose_file.keys():
                if self.docker_compose_file[k]["services"][s]["ports"]:
                    ports = self.docker_compose_file[k]["services"][s]["ports"]
                    self.ports[s] = ports

    def set_repositories_and_tags(self) -> None:
        for s in self.services:
            for k in self.docker_compose_file.keys():
                if self.docker_compose_file[k]["services"][s]["image"]:
                    image = self.docker_compose_file[k]["services"][s]["image"]
                    splited_image = image.split(":")
                    if len(splited_image) == 1:
                        repo = splited_image[0]
                        tag = "latest"
                    elif len(splited_image) == 2:
                        repo, tag = splited_image
                    if len(repo.split("/")) == 1:
                        repo = f"localhost/{repo}"
                    self.repositories[s] = repo
                    self.tags[s] = tag

    def __init__(self, args: argparse.Namespace) -> None:
        self.set_kube_name(args)
        self.namespace_dir = Path(f"{args.dir}/{args.namespace}")
        self.kube_dir = self.namespace_dir / self.kube_name
        self.deploy_dir = self.kube_dir / args.type.capitalize()
        Dir.mkdir(self.deploy_dir)
        self.set_docker_compose_file(args)
        if args.verbose:
            print("Generate list of services in docker-compose file")
        self.set_services()
        if args.verbose:
            print("Generate a POD manifest based on the specified POD")
        self.k8s_service_file = PodmanKube.generate(args.pod_name, True)
        if not self.k8s_service_file:
            raise Exception(f"POD with name {args.pod_name} is missing")
        if args.verbose:
            print("Replace symbols _ to - in yml elements ending with name(Name)")
        self.k8s_service_file = self.parse_yaml(self.k8s_service_file)
        self.k8s_service_file_with_correct_names = (
            self.replace_underscores_in_names_elements(
                copy.deepcopy(self.k8s_service_file)
            )
        )
        if args.verbose:
            print(f"Get descriptions of the environment variables")
        self.set_environments()
        if args.verbose:
            print(f"Get descriptions of the ports")
        self.set_ports()
        self.set_repositories_and_tags()


class PersistentVolumes(Default):
    """Class for PersistentVolume and PersistentVolumeClaim generation"""

    volumes = []

    def set_volumes(self, args: argparse.Namespace) -> None:
        for k in self.k8s_service_file_with_correct_names.keys():
            if self.k8s_service_file_with_correct_names[k]["kind"] == "Pod":
                for n in self.k8s_service_file_with_correct_names[k]["spec"]["volumes"]:
                    volume = PodmanKube.generate(n["name"], False)
                    volume = self.parse_yaml(volume)
                    volume = self.replace_underscores_in_names_elements(volume)["0"]
                    # volume have only one section
                    result_volume = dict()
                    result_volume["file"] = volume
                    name = n["persistentVolumeClaim"]["claimName"]
                    result_volume["name"] = name
                    result_volume["size"] = volume["spec"]["resources"]["requests"][
                        "storage"
                    ]
                    result_volume["path"] = f"{args.pvpath}/{args.namespace}/{name}"
                    result_volume["volume_section"] = n
                for c in self.k8s_service_file_with_correct_names[k]["spec"][
                    "containers"
                ]:
                    if "args" in c.keys():
                        result_volume["security_context"] = c["securityContext"]
                        result_volume["volume_mounts"] = c["volumeMounts"]
                self.volumes.append(result_volume)

    def gen_persistent_volume(self, args: argparse.Namespace, volume: dict) -> dict:
        """Generate persistent volume file"""
        persistent_volume_file = {
            "apiVersion": "v1",
            "kind": "PersistentVolume",
            "metadata": {
                "name": f"{args.namespace}-{volume['name']}",
                "labels": {"type": "local"},
            },
            "spec": {
                "storageClassName": "manual",
                "claimRef": {
                    "name": volume["name"],
                    "namespace": args.namespace,
                },
                "capacity": {"storage": volume["size"]},
                "accessModes": ["ReadWriteOnce"],
                "hostPath": {"path": volume["path"]},
            },
        }
        return persistent_volume_file

    def gen_persistent_volume_clame(
        self, args: argparse.Namespace, volume: dict
    ) -> dict:
        """Generate persistent volume file from volume file"""
        volume["file"]["metadata"]["namespace"] = args.namespace
        volume["file"]["spec"]["storageClassName"] = "manual"
        return volume["file"]

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.persistent_volume_claim_dir = self.deploy_dir / "PersistentVolumeClaim"
        self.persistent_volume_dir = self.deploy_dir / "PersistentVolume"
        if args.type != "helm":
            Dir.mkdir(self.persistent_volume_claim_dir)
        Dir.mkdir(self.persistent_volume_dir)
        if args.verbose:
            print("Generate PersistentVolumeClaims and PersistentVolumes:")
        self.set_volumes(args)
        for v in self.volumes:
            if args.type == "helm":
                for s in self.services:
                    if s in v["name"]:
                        self.persistent_volume_claim_dir = (
                            self.deploy_dir / "charts" / s / "templates"
                        )
                        Dir.mkdir(self.persistent_volume_claim_dir)
            persistent_volume_claim_file = self.gen_persistent_volume_clame(args, v)
            File.create(
                self.persistent_volume_claim_dir,
                "persistentvolumeclaim" if args.type == "helm" else v["name"],
                args.output,
                persistent_volume_claim_file,
            )
            if args.verbose:
                print(
                    f"\tFile {self.persistent_volume_claim_dir}/{v['name']}.{args.output} was created"
                )
            persistent_volume_file = self.gen_persistent_volume(args, v)
            name = f"{args.namespace}-{v['name']}"
            File.create(
                self.persistent_volume_dir, name, args.output, persistent_volume_file
            )
            if args.verbose:
                print(
                    f"\tFile {self.persistent_volume_dir}/{name}.{args.output} was created"
                )
            Dir.mkdir(v["path"])
            if args.user:
                os.chown(
                    v["path"],
                    pwd.getpwnam(args.user).pw_uid,
                    pwd.getpwnam(args.group).pw_gid,
                )
            if args.verbose:
                print(f"\tDirectory {v['path']} was created")


class Deployment(PersistentVolumes):
    """Class for Deployment generation"""

    def gen_deploy_file(
        self, args: argparse.Namespace, pod_section: dict, service: str
    ) -> dict:
        """Generate deploy file"""
        deploy_file = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": service,
                "labels": {"app": service},
                "namespace": args.namespace,
            },
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": {"app": service}},
                "template": {
                    "metadata": {"labels": {"app": service}},
                    "spec": dict(),
                },
            },
        }
        for v in self.volumes:
            if service in v["name"]:
                if "volumes" not in deploy_file["spec"]["template"]["spec"].keys():
                    deploy_file["spec"]["template"]["spec"]["volumes"] = []
                deploy_file["spec"]["template"]["spec"]["volumes"] = [
                    v["volume_section"]
                ]
        containers = pod_section["spec"]["containers"]
        for c in containers:
            if service in c["name"]:
                if "containers" not in deploy_file["spec"]["template"]["spec"].keys():
                    deploy_file["spec"]["template"]["spec"]["containers"] = []
                deploy_file["spec"]["template"]["spec"]["containers"].append(c)

        return deploy_file

    def gen_service_file(
        self, args: argparse.Namespace, service: str, service_section: dict
    ) -> dict:
        """Generate service file"""
        ports = []
        for p in self.ports[service]:
            for port in service_section["spec"]["ports"]:
                if port["port"] == int(str(p).split(":")[-1]):
                    ports.append(port)
        service_section["spec"]["ports"] = ports
        service_section["metadata"]["name"] = service
        service_section["metadata"]["labels"]["app"] = service
        service_section["metadata"]["namespace"] = args.namespace
        service_section["spec"]["selector"]["app"] = service
        return service_section

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.service_dir = self.deploy_dir / "Service"
        Dir.mkdir(self.service_dir)
        for k in self.k8s_service_file.keys():
            if self.k8s_service_file[k]["kind"] == "Pod":
                pod_section = self.k8s_service_file_with_correct_names[k]
            elif self.k8s_service_file[k]["kind"] == "Service":
                service_section = self.k8s_service_file_with_correct_names[k]
        for s in self.services:
            deploy_file = self.gen_deploy_file(args, pod_section, s)
            File.create(self.deploy_dir, s, args.output, deploy_file)
            service_file = self.gen_service_file(
                args, s, copy.deepcopy(service_section)
            )
            File.create(self.service_dir, s, args.output, service_file)


class Helm(PersistentVolumes):
    """Class for helm generation"""

    app_version = "1.16.0"
    dependencies = []
    main_values_file = dict()
    version = "0.1.0"

    @staticmethod
    def create(service: str, service_chart_dir_path: Path) -> None:
        """helm create"""
        try:
            cmd = f"helm create {service}"
            output = os.popen(cmd)
            status = output.close()
            if status:
                raise Exception(f"cmd return {status}")
            output = os.popen(f"rm -f {service}/Chart.yaml {service}/values.yaml")
            status = output.close()
            if status:
                raise Exception(f"rm return {status}")
            for fp in ["*", ".*"]:
                output = os.popen(f"cp -r {service}/{fp} {service_chart_dir_path}")
                status = output.close()
                if status:
                    raise Exception(f"cp return {status}")
        except:
            raise Exception(f'Service "{service}" does not exists')

    def gen_chart_file(self, service: str) -> dict:
        chart_file = {
            "apiVersion": "v2",
            "name": service,
            "description": f"A Helm chart for {service}",
            "version": self.version,
            "appVersion": self.app_version,
        }
        return chart_file

    def add_dependency(self, service: str) -> None:
        self.dependencies.append(
            {
                "name": service,
                "version": self.version,
                "repository": f"file://./{service}",
                "enabled": True,
            }
        )

    def gen_hosts(self, service: str) -> list[dict]:
        """Generate hosts section"""
        hosts = {
            "host": f"{service}.local",
            "paths": [{"path": "/", "pathType": "ImplementationSpecific"}],
        }
        return hosts

    def gen_values_file(self, service: str) -> dict:
        for p in self.ports[service]:
            port = int(str(p).split(":")[-1])
        values_file = {
            "replicaCount": 1,
            "image": {
                "repository": self.repositories[service],
                "tag": self.tags[service],
                "pullPolicy": "IfNotPresent",
            },
            "imagePullSecrets": [],
            "nameOverride": "",
            "serviceAccount": {"name": service, "create": True, "annotations": {}},
            "podAnnotations": {},
            "podSecurityContext": {},
            "securityContext": {},
            "service": {"port": port, "type": "ClusterIP"},
            "ingress": {
                "hosts": [self.gen_hosts(service)],
                "enabled": False,
                "className": "",
                "annotations": {},
                "tls": [],
            },
            "resources": {},
            "autoscaling": {
                "enabled": False,
                "minReplicas": 1,
                "maxReplicas": 100,
                "targetCPUUtilizationPercentage": 80,
            },
            "nodeSelector": {},
            "tolerations": [],
            "affinity": {},
            "fullnameOverride": service,
        }
        if self.environments[service]:
            values_file["env"] = self.environments[service]
        for v in self.volumes:
            if service in v["name"]:
                values_file["volumes"] = [v["volume_section"]]
                values_file["volumeMounts"] = v["volume_mounts"]
                values_file["securityContext"] = v["security_context"]
        return values_file

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.charts_dir = self.deploy_dir / "charts"
        Dir.mkdir(self.charts_dir)
        for s in self.services:
            self.main_values_file[s] = dict()
            if args.verbose:
                print(f"Create files for service: {s}")
            service_chart_dir_path = self.charts_dir / s
            Dir.mkdir(service_chart_dir_path)
            self.create(s, service_chart_dir_path)
            if args.verbose:
                print(f"\tTemplate files was created")
            service_chart_file = self.gen_chart_file(s)
            service_chart_file["type"] = "application"
            File.create(
                service_chart_dir_path, "Chart", args.output, service_chart_file
            )
            if args.verbose:
                print(
                    f"\tFile {service_chart_dir_path}/Chart.{args.output} was created"
                )
            values_file = self.gen_values_file(s)
            File.create(service_chart_dir_path, "values", args.output, values_file)
            if args.verbose:
                print(
                    f"\tFile {service_chart_dir_path}/values.{args.output} was created"
                )
            self.add_dependency(s)
        main_chart_file = self.gen_chart_file(self.kube_name)
        main_chart_file["dependencies"] = self.dependencies
        File.create(self.deploy_dir, "Chart", args.output, main_chart_file)
        if args.verbose:
            print(f"File {self.deploy_dir}/Chart.{args.output} was created")
        File.create(self.deploy_dir, "values", args.output, self.main_values_file)
        if args.verbose:
            print(f"File {self.deploy_dir}/values.{args.output} was created")


class Pod(PersistentVolumes):
    """Class for Pod generation"""

    def gen_deploy_file(self, args: argparse.Namespace, pod_file: dict) -> dict:
        """Generate deploy file from pod file"""
        pod_file["metadata"]["name"] = self.kube_name
        pod_file["metadata"]["labels"]["app"] = self.kube_name
        pod_file["metadata"]["namespace"] = args.namespace
        pod_file["spec"]["hostAliases"] = [
            {"ip": "127.0.0.1", "hostnames": self.services}
        ]
        return pod_file

    def gen_service_file(self, args: argparse.Namespace, service_section: dict) -> dict:
        """Generate service file from service section"""
        service_section["metadata"]["name"] = self.kube_name
        service_section["metadata"]["namespace"] = args.namespace
        service_section["metadata"]["labels"]["app"] = self.kube_name
        service_section["spec"]["selector"]["app"] = self.kube_name
        return service_section

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.service_dir = self.deploy_dir / "Service"
        Dir.mkdir(self.service_dir)
        for k in self.k8s_service_file.keys():
            if self.k8s_service_file[k]["kind"] == "Pod":
                pod_section = self.k8s_service_file_with_correct_names[k]
            elif self.k8s_service_file[k]["kind"] == "Service":
                service_section = self.k8s_service_file_with_correct_names[k]
        deploy_file = self.gen_deploy_file(args, pod_section)
        File.create(self.deploy_dir, self.kube_name, args.output, deploy_file)
        if args.verbose:
            print(
                f"Deploy file {self.deploy_dir}/{self.kube_name}.{args.output} was created"
            )
        service_file = self.gen_service_file(args, service_section)
        File.create(self.service_dir, self.kube_name, args.output, service_file)
        if args.verbose:
            print(
                f"Service file {self.service_dir}/{self.kube_name}.{args.output} was created"
            )


class Util:
    """Contains CLI Util"""

    def __init__(self) -> None:
        self.args = ArgsParser().get_args()
        match self.args.type:
            case "deployment":
                Deployment(self.args)
            case "helm":
                Helm(self.args)
            case "pod":
                Pod(self.args)


def main() -> None:
    Util()


if __name__ == "__main__":
    main()