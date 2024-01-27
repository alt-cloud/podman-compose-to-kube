podman-compose-to-kube(1) -- generate kubernetes manifests based on the running podman-compose POD
================================

## SYNOPSIS
<pre>
podman-compose-to-kube\
   [--type(-t) &lt;deployment type>]\
   [--namespace(-n) &lt;namespace>]
   [--dir(-d) &lt;manifests_directory>]\
   [--pvpath &lt;PersistentVolume_directory>] \
   [--user &lt;rootless_user>]\
   [--group &lt;rootless_group>]\
   [--debug &lt;debug_level>]\
   &lt;POD_name>\
   &lt;docker-compose_file_name>
</pre>

## DESCRIPTION

The script provides the migration of docker-compose solutions to kubernetes.

Before calling the script, you need to use the podman-compose command to start the service stack in POD and check its functionality .


The script podman-compose-to-kube generates `kubernetes manifests` to deploy the specified service stack
in kubernetes.
The `POD` created by the podman-compose command is used as the basis for generation.

Manifests are generated in the directory specified by the `--dir` (`-d`) option (the default is the `manifests` directory).
The manifest directory has the following structure:
<pre>
manifests/
├── &lt;namespace1>
│   ├── &lt;pod1Name>
│   │   ├── Deployment
│   │   │   ├── &lt;service1Name>.yml
│   │   │   ├── &lt;service2Name>.yml
│   │   │   ├── PersistentVolume
│   │   │   │   └── &lt;namespace1>-&lt;pod1Name>-&lt;service1Name>.yml
│   │   │   ├── PersistentVolumeClaim
│   │   │   │   └── &lt;pod1Name>-&lt;service1Name>.yml
│   │   │   └── Service
│   │   │       ├── &lt;service1Name>.yml
│   │   │       └── &lt;service2Name>.yml
│   │   └── Pod
│   │       ├── &lt;pod1Name>.yml
│   │       ├── PersistentVolume
│   │       │   └── &lt;namespace1>-&lt;pod1Name>-&lt;service1Name>.yml
│   │       ├── PersistentVolumeClaim
│   │       │   └── &lt;pod1Name>-&lt;service1Name>.yml
│   │       └── Service
│   │           └── &lt;pod1Name>.yml
│   └── &lt;pod2Name>
│       ├── Deployment
│       │   ├── ...
│       └── Pod
│           ├── ...
└── &lt;namespace2>
    └── &lt;pod3Name>
        └── ...
</pre>

The manifests directory (default `manifests`) contains `namespaces` subdirectories.

Within the `namespace` directory, for each generated set of manifests, a subdirectory is created for each `Pod`.
The directory name is formed from the `Pod` name by removing the `pod` prefix.

In the `Pod` directory, for each deployment type (`Pod`, `Deployment`), a subdirectory is created containing YML manifest files:

- manifest files `*.yml` - container deployment files (`kind: Pod`, `kind: Deployment`);
- `Service` directory with YML files describing services (`kind: Service`);
- the `PersistentVolumeClaim` directory with YML files describing requests for external volumes (`kind: PersistentVolumeClaim`);
- `PersistentVolume` directory with YML files describing external local volumes (`kind: PersistentVolume`).

Files in the `PersistentVolume` directory descrbe external local volumes. They have links to the corresponding YML files - descriptions of requests for external volumes in the `PersistentVolumeClaim` directory.

This format for placing YML manifest files allows you to deploy a kubernetes solution with one command:
<pre>
kubectl apply -R -f manifests/&lt;namespace1>/&lt;podName>/Pod
</pre>
for POD deployment or
<pre>
kubectl apply -R -f manifests/&lt;namespace1>/&lt;podName>/Deployment
</pre>
for Deployment deployment.
<br>
<br>
And also remove the kubernet solution:
<pre>
kubectl delete -R -f manifests/&lt;namespace1>/&lt;podName>/Pod
</pre>
for POD deployment or
<pre>
kubectl delete -R -f manifests/&lt;namespace1>/&lt;podName>/Deployment
</pre>
for Deployment deployment.


### POD Deployment Type

**Deploy file of type Pod (kind: Pod)**


With deployment type `POD` (`--type pod` or `-t p`) in the directory `manifests/<namespace>/<podName>/Pod/`
a deployment YML file (`kind: Pod`) `<pod1Name>.yml` is generated.

All `docker-compose service` containers run within the one pod.
Network interaction between containers of the same service stack is carried out through the localhost interface (127.0.0.1).
In this regard, a description is added to the YML file:
<pre>
   hostAliases:
     - ip: 127.0.0.1
       hostnames:
         - &lt;service_name1>
         - &lt;service_name2>
         - ...
</pre>
This provides the ability to access service ports by service name.

**Service description file (kind: Service)**

The service description file `<podName>.yml` is generated in the `manifests/<namespace>/<podName>/Pod/Service/` directory.
All docker service ports are placed into one service named `<podName>` in the namespace `<namespace>`.
This provides access to `Pod' ports by domain names within the kubernetes cluster:
<pre>
&lt;podName> (within namespace `&lt;namespace>`)
&lt;podName>.&lt;namespace>
&lt;podName>.&lt;namespace>.svc.cluster.local
</pre>

**External volume request description files (kind: PersistentVolumeClaim)**

External volume request description files with names `<podName>-<serviceName>` are located in the directory
`manifests/<namespace>/<podName>/Pod/PersistentVolumeClaim/`.
Each volume is named `<podName>-<serviceName>`.
Amount of allocated disk memory: `1Gi`.
If necessary, after generating the YML files, this parameter can be changed.

**Local volume description files (kind: PersistentVolume)**

For each request for an external volume, a local volume description file named `<namespace>-<podName>-<serviceName>.yml` is generated in the `manifests/<namespace>/<podName>/Pod/PersistentVolume/` directory.
Each described volume has the same size (`1Gi`) as the claim for the outer volume and is associated with it through a handle:
<pre>
   claimRef:
     name: &lt;podName>-&lt;serviceName>
     namespace: &ltnamespace>
</pre>

The subdirectories of the created volumes are located in the `<namespace>` directory of the directory specified by the `--pvpath` option (default `/mnt/PersistentVolumes`). Subdirectory name: `<podName>-<serviceName>`.

If volumes are created for a `kubernetes` node running in `rootless mode`, you must specify the name and group in the `--user(-u)`, `--group`(-g)` parameters (if there is no flag, the same as username) on behalf of which the containers of the cluster node operate.

### Deployment type

**Deploy files of type Deployment (kind: Deployment)**

When the deployment type is `Deployment` (`--type deployment` or `-t d`) in the `manifests/<namespace>/<podName>/Deployment/` directory, for each docker-compose service a deployment YML file (` kind: Deployment`) `servuceName>.yml` is created.

The number of service replicas (`spec.replicas`) is set to 1.

If necessary, after generating YML files for `Stateless containers` (without external volumes or with read-only volumes), the number of replicas can be increased to the required value.

**Service description files (kind: Service)**

Service description files `<serviceName>.yml` are generated in the `manifests/<namespace>/<podName>/Deployment/Service/` directory.

It should be noted that if the `docker-compose service` accepts requests on any port from other services in the service stack, before starting the `Pod` with the `podman-compose` command it is necessary to **be sure to specify this port in the descriptor** ` services.<service>.port` `docker-compose file`.
Otherwise, the service description file `manifests/<namespace>/<podName>/Deployment/Service/<serviceName>.yml` will not be created and the container ports will not be visible under the short domain name `<serviceName>` by other containers of this deployment ( `Deployment`).

**External Volume Claim Files (kind: PersistentVolumeClaim) and Local Volume Claim Files (kind: PersistentVolume)**

These files are generated in exactly the same way. as for `Pod` type deployment.
Moreover, files created by a `Pod` deployment can be used by a `Deployment` deployment.
And vice versa.
But you should not use these volumes simultaneously for both deployments.


##OPTIONS

Team flags:

* `--type` (`-t`) - deployment type: `pod` (`p`), `deployment` (`d`). The default value is `pod`.
* `--namespace` (`-n`) - kubernetes namespace. The default value is `default`.
* `--dir` (`-d`) - directory for generated manifests. The default value is `manifests`.
* `-pvpath` - directory for mounting PersistentVolume volumes. The default value is `/mnt/PersistentVolumes/`.
* `--user` (`-u`) the name of the rootless user from which kubernetes runs. The default value is the empty string.
* `--group` (`-g`) - group of the rootless user from which kubernetes runs. The default value is `=user`.
* `--debug` - debug level. The default value is `0`.

Positional parameters:

1. POD_name - the name of the `POD`;
2. docker-compose-filename - the name of the docker-compose file from which `POD` is deployed
