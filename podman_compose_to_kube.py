#!/usr/bin/python3

import argparse
import copy
import json
import os
import pwd

import yaml

__version__ = "2.0.0"


class Info:
    def __init__(
        self, kube_name, deploy_dir, service_dir, volume_dir, persistent_volume_dir
    ) -> None:
        self.kube_name = kube_name
        self.deploy_dir = deploy_dir
        self.service_dir = service_dir
        self.volume_dir = volume_dir
        self.persistent_volume_dir = persistent_volume_dir

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Podman compose to k8s")
    parser.add_argument(
        "-t",
        "--type",
        type=str,
        choices=["pod", "p", "deployment", "d"],
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
        help="output files format"
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

def set_default_group(args: argparse.Namespace):
    if args.group == "":
        args.group = args.user

def set_type(args: argparse.Namespace):
    if args.type == "p":
        args.type = "pod"
    if args.type == "d":
        args.type = "deployment"

def args_check(args: argparse.Namespace):
    if args.pod_name[:3] != "pod":
        print("Incorrect POD name")
        raise

def set_kube_name(args: argparse.Namespace) -> str:
    if args.pod_name[:3] == "pod":
        kube_name = args.pod_name[3:]
        if kube_name[0] == "-" or kube_name[0] == "_":
            kube_name = kube_name[1:]
    return kube_name

def mkdirs(dirs: list[str]) -> None:
    for d in dirs:
        if d[0] == '/':
            path = d
        else:
            path = os.path.join(os.getcwd(), d)
        try:
            os.mkdir(path)
        except FileExistsError:
            pass

def generate_a_k8s_service_file(pod_name: str) -> str:
    try:
        rez = ""
        cmd = f"podman kube generate --service {pod_name}"
        output = os.popen(cmd, "r")
        for l in output:
            rez += l
        status = output.close()
        if status:
            raise
        return rez
    except:
        print(f'Service "{pod_name}" does not exists')
        raise

def parse_yaml(yaml_file: str) -> dict:
    rez = dict()
    c = 0
    yamls = yaml.load_all(yaml_file, yaml.FullLoader)
    for y in yamls:
        rez[f"{c}"] = y
        c += 1
    return rez

def replace_underscores_in_names_elements(yaml_section: dict) -> dict:
    if isinstance(yaml_section, str) or isinstance(yaml_section, int):
        return yaml_section
    for k in yaml_section.keys():
        yaml_param = yaml_section[k]
        if isinstance(yaml_param, list):
            for i in yaml_section[k]:
                replace_underscores_in_names_elements(i)
        if isinstance(yaml_param, dict):
            replace_underscores_in_names_elements(yaml_section[k])
        if "name" in k.lower():
            yaml_section[k] = yaml_param.replace("_", "-")
    return yaml_section

def read_file(path: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        print(f'File "{path}" not found')
        raise

def get_services_names(yaml_section: dict) -> list:
    rez = []
    for k in yaml_section.keys():
        rez += yaml_section[k]["services"].keys()
    return rez

def get_environment_from_service(compose_section: dict, service: str) -> list:
    environment = []
    if "environment" in compose_section["services"][service].keys():
        env = compose_section["services"][service]["environment"]
        for e in env.keys():
            environment.append({"name": e, "value": f"{env[e]}"})
    return environment

def get_volume_names(yaml_section: dict) -> list:
    volume_names = []
    for n in yaml_section["spec"]["volumes"]:
        volume_names.append(n["persistentVolumeClaim"]["claimName"])
    return volume_names

def podman_kube_generate(volume_name: str) -> str:
    try:
        rez = ""
        cmd = f"podman kube generate {volume_name}"
        output = os.popen(cmd, "r")
        for l in output:
            rez += l
        status = output.close()
        if status:
            raise
        return rez
    except:
        print(f'Volume "{volume_name}" does not exists')
        raise

def write_yaml_to_file(yaml_section: dict, file_path: str, args: argparse.Namespace) -> None:
    if args.output == 'yml':
        yaml.Dumper.ignore_aliases = lambda *args: True
        file_info = "# Created with podman-compose-to-kube 1.0.0-alt1\n"
        file_info += "---\n"
        file_info += yaml.dump(yaml_section, default_flow_style=False, default_style='')
    elif args.output == 'json':
        file_info = json.dumps(yaml_section, indent=2)
    with open(file_path, "w") as f:
        f.write(file_info)

def gen_persistent_volume_file(
    name: str, claim_ref_name: str, size: str, path: str, args: argparse.Namespace
) -> dict:
    pv = {
        "apiVersion": "v1",
        "kind": "PersistentVolume",
        "metadata": {"name": name, "labels": {"type": "local"}},
        "spec": {
            "storageClassName": "manual",
            "claimRef": {"name": claim_ref_name, "namespace": args.namespace},
            "capacity": {"storage": size},
            "accessModes": ["ReadWriteOnce"],
            "hostPath": {"path": path},
        },
    }
    return pv

def get_deploy_file(name: str, containers: dict, args: argparse.Namespace) -> dict:
    deploy = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "labels": {"app": name},
            "namespace": args.namespace,
        },
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": {"app": name}},
                "spec": {"containers": [containers]},
            },
        },
    }
    return deploy

def set_environment(service_file: dict, environment: list) -> dict:
    for j in range(len(service_file["spec"]["containers"])):
        if "env" in service_file["spec"]["containers"][j].keys():
            service_file["spec"]["containers"][j]["env"] = environment
    return service_file

def gen_deploy_file_of_the_pod(pod_file: dict, services: list, args: argparse.Namespace, info: Info) -> None:
    deploy_file_path = f"{info.deploy_dir}/{info.kube_name}.{args.output}"
    if args.verbose:
        print(f"Generate a deploy file {deploy_file_path} of the Pod type:")
    pod_file["metadata"]["name"] = info.kube_name
    pod_file["metadata"]["labels"]["app"] = info.kube_name
    pod_file["metadata"]["namespace"] = args.namespace
    pod_file["spec"]["hostAliases"] = [{"ip": "127.0.0.1", "hostnames": services}]
    write_yaml_to_file(pod_file, deploy_file_path, args)

def gen_service_file_of_the_pod(service_file: dict, args: argparse.Namespace, info: Info) -> None:
    service_file_path = f"{info.service_dir}/{info.kube_name}.{args.output}"
    if args.verbose:
        print(f"Generate a service file {service_file_path} of the Pod type")
    service_file["metadata"]["name"] = info.kube_name
    service_file["metadata"]["namespace"] = args.namespace
    service_file["metadata"]["labels"]["app"] = info.kube_name
    service_file["spec"]["selector"]["app"] = info.kube_name
    write_yaml_to_file(service_file, service_file_path, args)

def gen_pvs(service_file: dict, args: argparse.Namespace, info: Info) -> None:
    if "volumes" in service_file["spec"].keys():
        if args.verbose:
            print("Generate PersistentVolumeClaims and PersistentVolumes:")
        volume_names = get_volume_names(service_file)
        for vn in volume_names:
            volume_file_path = f"{info.volume_dir}/{vn}.{args.output}"
            volume_yaml = podman_kube_generate(vn)
            volume = parse_yaml(volume_yaml)
            volume = replace_underscores_in_names_elements(volume)
            for v in volume.keys():
                volume[v]["metadata"]["namespace"] = args.namespace
                volume[v]["spec"]["storageClassName"] = "manual"
                write_yaml_to_file(volume[v], volume_file_path, args)
                pv_size = volume[v]["spec"]["resources"]["requests"]["storage"]
                pv_name = f"{args.namespace}-{vn}"
                pv_file = f"{info.persistent_volume_dir}/{pv_name}.{args.output}"
                pv_path = f"{args.pvpath}/{args.namespace}/{vn}"
                if args.verbose:
                    print(f"\t{volume_file_path}")
                    print(f"\t{pv_file}")
                    print(f"\t{pv_path}")
                mkdirs([f"{args.pvpath}/{args.namespace}", pv_path])
                if args.user:
                    os.chown(
                        pv_path,
                        pwd.getpwnam(args.user).pw_uid,
                        pwd.getpwnam(args.group).pw_gid
                    )
                pv_path = pv_path if pv_path[0] == '/' else os.path.join(os.getcwd(), pv_path)
                persistent_volume = gen_persistent_volume_file(
                    pv_name, vn, pv_size, pv_path, args
                )
                write_yaml_to_file(persistent_volume, pv_file, args)

def get_ports(compose_file: dict, service: str, args: argparse.Namespace) -> list:
    if compose_file["services"][service]["ports"]:
        if args.verbose:
            print("\t\tAdd descriptions of the ports to the service")
        ports = compose_file["services"][service]["ports"]
        return ports

def gen_service_files(compose: dict, k8s_service_file: dict, service: str, args: argparse.Namespace, info: Info) -> None:
    for i in compose.keys():
        ports = get_ports(compose[i], service, args)
        service_file_path = f"{info.service_dir}/{service}.{args.output}"
        if args.verbose:
            print(f"\t\tGenerate a service file {service_file_path}")
        for e in k8s_service_file.keys():
            if k8s_service_file[e]["kind"] == "Service":
                ps = []
                for p in ports:
                    for port in k8s_service_file[e]["spec"]["ports"]:
                        if port["port"] == int(str(p).split(':')[-1]):
                            ps.append(port)
                service_file = copy.deepcopy(k8s_service_file[e])
                service_file["spec"]["ports"] = ps
                service_file["metadata"]["name"] = service
                service_file["metadata"]["labels"]["app"] = service
                service_file["metadata"]["namespace"] = args.namespace
                service_file["spec"]["selector"]["app"] = service
                write_yaml_to_file(service_file, service_file_path, args)

def gen_deploy_file(
    pod_file: dict, service: str, args: argparse.Namespace, info: Info
) -> None:
    if args.verbose:
        print(f"\t{service}")
    volumes = pod_file["spec"]["volumes"]
    for v in volumes:
        volume = v["name"]
        deploy_file_path = f"{info.deploy_dir}/{service}.{args.output}"
        containers = pod_file["spec"]["containers"]
        for c in containers:
            if service in c["name"]:
                deploy = get_deploy_file(service, c, args)
        if service in volume:
            if args.verbose:
                print("\t\tAdd volume descriptions to the container")
            deploy["spec"]["template"]["spec"]["volumes"] = [v]
        if args.verbose:
            print(f"\t\tGenerate a deploy file {deploy_file_path}")
        write_yaml_to_file(deploy, deploy_file_path, args)

def main() -> None:
    args = parse_args()
    set_default_group(args)
    set_type(args)
    args_check(args)
    kube_name = set_kube_name(args)
    namespace_dir = f"{args.dir}/{args.namespace}"
    kube_dir = f"{namespace_dir}/{kube_name}"
    deploy_dir = f"{kube_dir}/{args.type.capitalize()}"
    service_dir = f"{deploy_dir}/Service"
    volume_dir = f"{deploy_dir}/PersistentVolumeClaim"
    persistent_volume_dir = f"{deploy_dir}/PersistentVolume"
    info = Info(kube_name, deploy_dir, service_dir, volume_dir, persistent_volume_dir)
    dirs = [
        args.dir,
        namespace_dir,
        kube_dir,
        deploy_dir,
        service_dir,
        args.pvpath,
        persistent_volume_dir,
        volume_dir,
    ]
    mkdirs(dirs)
    if args.verbose:
        print("Generate a POD manifest based on the specified POD")
    k8s_service_file = generate_a_k8s_service_file(args.pod_name)
    if not k8s_service_file:
        print("POD with name {args.pod_name} is missing")
        return
    if args.verbose:
        print("Replace symbols _ to - in yml elements ending with name(Name)")
    k8s_service_file = parse_yaml(k8s_service_file)
    k8s_service_file_with_correct_names = replace_underscores_in_names_elements(k8s_service_file)
    if args.verbose:
        print("Generate list of services in docker-compose file")
    compose_file = read_file(args.docker_compose_file_name)
    compose = parse_yaml(compose_file)
    compose = replace_underscores_in_names_elements(compose)
    services = get_services_names(compose)
    if args.verbose:
        print(f"Get descriptions of the environment variables")
    for k in compose.keys():
        for s in services:
            environment = get_environment_from_service(compose[k], s)
    if args.verbose:
        print("Generate common POD file")
    for i in k8s_service_file.keys():
        if k8s_service_file[i]["kind"] == "Pod":
            pod_file = set_environment(k8s_service_file_with_correct_names[i], environment)
            gen_pvs(k8s_service_file[i], args, info)
        if k8s_service_file[i]["kind"] == "Service":
            service_file = k8s_service_file_with_correct_names[i]
    if args.type == "pod":
        gen_deploy_file_of_the_pod(pod_file, services, args, info)
        gen_service_file_of_the_pod(service_file, args, info)
    elif args.type == "deployment":
        if args.verbose:
            print("Generate a deploy files of the Deployment type:")
        for s in services:
            gen_deploy_file(pod_file, s, args, info)
            gen_service_files(compose, k8s_service_file_with_correct_names, s, args, info)

if __name__ == "__main__":
    main()