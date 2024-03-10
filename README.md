+# podman-compose-to-kube - tool of migrating docker-compose solutions to kubernetes

One of the main problems on `docker-compose` (`docker swarm`) migration
solutions in `kubernetes` is the generation of `kubernetes-manifests` from
`YAML files describing the service stack`. There is quite a poor one
a set of tools that solves this problem. This document describes
solving this problem by using commands
[podman-compose](https://github.com/containers/podman-compose) and
[podman-compose-to-kube](https://github.com/alt-cloud/podman-compose-to-kube).

An example of stack deployments will be used
`docker-compose` stack of
[hello-python](https://github.com/containers/podman-compose/tree/devel/examples/hello-python)
project `podman-compose`.

Describes options for deploying both `rootfull` and
`rootless solutions`.


## Deploying docker-compose stack into podman-compose

### Loading hello-python service stack description

Copy the contents of the directory
[hello-python](https://github.com/containers/podman-compose/tree/devel/examples/hello-python).

If you have git installed, this can be done with the commands:
```
# git clone -n --depth=1 --filter=tree:0 https://github.com/containers/podman-compose.git
# cd podman-compose/
# git sparse-checkout set --no-cone examples/hello-python
# git checkout
```
After executing commands in the directory
`podman-compose/examples/hello-python` will expand the contents of the specified
above the catalogue.

### Deploying a service stack

#### Description of the service stack

Go to the `podman-compose/examples/hello-python` directory. In the catalog
there is a file `docker-compose.yml` describing the service stack:
```
version: '3'
volumes:
  redis:
services:
  redis:
    read_only: true
    image: docker.io/redis:alpine
    command: ["redis-server", "--appendonly", "yes", "--notify-keyspace-events", "Ex"]
    volumes:
    - redis:/data
  web:
    read_only: true
    build:
      context: .
    image: hello-py-aioweb
    ports:
    - 8080:8080
    environment:
      REDIS_HOST: redis
```

The `redis` service starts a container with a `redis` volume and a port for
external access `6379`.

The `web` service collects the `hello-py-aioweb` image.
The image is named `localhost/hello-py-aioweb`.
Based on it, a container is created that supports receiving HTTP requests on port `8080`.
The `localhost/hello-py-aioweb` image is built based on the `Dockerfile`:
```
FROM python:3.9-alpine

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "-m", "app.web" ]
EXPOSE 8080
```

When the container starts, the python script `app/web.py` is launched.
The script accepts HTTP requests and generates a request counter in the redis database.
The response is a text containing the request number in the database.

#### Deployment a service stack

Before starting the service stack, you need to clarify the file
`docker-compose.yml`:
```
version: '3'
volumes:
  redis:
  redis1:
services:
  redis:
    read_only: true
    image: docker.io/redis:alpine
    command: ["redis-server", "--appendonly", "yes", "--notify-keyspace-events", "Ex"]
    volumes:
    - redis:/data
    ports:
    - 6379
  web:
    read_only: true
    build:
      context: .
    image: hello-py-aioweb
    ports:
    - 8080:8080
    environment:
      REDIS_HOST: redis
      REDIS_PORT: 6379
```
Two changes have been made to the file:

1. A description of port `6379` has been added to the `redis` service.
2. A description of the variable `REDIS_PORT: 6379` has been added to the `web` service.

Both of these changes are necessary when deploying kubernet services to
`Deployment` mode.

The first change is due to the fact that if the port description is missing, then
will not be generated during generation due to lack of information
The `YML file describing the kubernet service` and the `redis container` will be
not accessible from the `web` container.

The second change is due to the fact that in the `Deployment` mode the container
`web` exports the `REDIS_PORT` variable in the format
`http://<ip>:<port>`. Application `App/web.py`
processes this value in `<port>` format.

To start the service stack, type the command:
```
podman-compose --in-pod counter -p counter up -d
```
*When using `podman-compose` version `>= 1.0.7` parameter `--in-pod` is optional.*

The `-p` parameter specifies the project name - the name suffix of `POD`
(`pod_counter`) and a prefix for container and volume names. If the `-p` option
missing, the name of the current directory is accepted as the project name
(in our case `hello-python`).

When running, `podman-compose` displays a list of commands to run:
```
...
podman volume inspect counter_redis || podman volume create counter_redis
...
podman pod create --name=pod_counter --infra=false --share=
...
podman run --name=counter_redis_1 -d --pod=pod_counter --read-only --label ...
...
podman run --name=counter_web_1 -d --pod=pod_counter --read-only --label ...
...
```
After deployment the POD and containers, the status can be viewed using commands:

- list of running PODs:
```
podman pod ls

POD ID        NAME         STATUS      CREATED        INFRA ID    # OF CONTAINERS
d37ba3addeb3  pod_counter  Running     9 minutes ago              2
```
- POD container logs:
```
podman pod logs pod_counter

b5bdc8d1977f 1:C 18 Jan 2024 11:04:20.309 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
...
b5bdc8d1977f 1:M 18 Jan 2024 11:04:20.312 * Ready to accept connections tcp
```

- List of running containers:
```
podman ps

CONTAINER ID  IMAGE                             COMMAND               CREATED         STATUS         PORTS                   NAMES
...
b5bdc8d1977f  docker.io/library/redis:alpine    redis-server --ap...  27 minutes ago  Up 27 minutes                          counter_redis_1
49f6f5141b24  localhost/hello-py-aioweb:latest  python -m App.web     27 minutes ago  Up 27 minutes  0.0.0.0:8080->8080/tcp  counter_web_1
...
```

- Redis database container logs
```
podman logs counter_redis_1

1:C 18 Jan 2024 11:04:20.309 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
...
1:M 18 Jan 2024 11:04:20.312 * Ready to accept connections tcp
```


- WEB interface container logs:
```
podman log counter_web_1
```

#### Checking the operation of the service stack

To check the operation of the stack, send requests sequentially with the `curl` command
to port `8080`:
```
# curl localhost:8080/
counter=1
# curl localhost:8080/
counter=2
# curl localhost:8080/
counter=3
...
```

## Exporting a running POD to kubernetes manifests and deployment them

### Deployment as a kubernetes POD

Manifests are generated using the `podman-compose-to-kube` command.
Format:
```
podman-compose-to-kube \
  [--type(-t) <deployment type>]\
  [--namespace(-n) <namespace>]
  [--dir(-d) <manifests_directory>]\
  [--pvpath <PersistentVolume_directory>] \
  [--user <rootless_user>]\
  [--group <rootless_group>]\
  [--output(-o) [yml|json]]\
  [--verbose(-v)]\
  <POD_name>\
  <docker-compose_file_name>
```

#### Manifest generation

Generating manifests for POD deployment is done with the command:
```
podman-compose-to-kube -v pod_counter docker-compose.yaml
```
```
Generate a POD manifest based on the specified POD
Replace symbols _ to - in yml elements ending with name(Name)
Generate list of services in docker-compose file
Get descriptions of the environment variables
Generate common POD file
Generate PersistentVolumeClaims and PersistentVolumes:
        manifests/default/counter/Pod/PersistentVolumeClaim/counter-redis.yml
        manifests/default/counter/Pod/PersistentVolume/default-counter-redis.yml
        /mnt/PersistentVolumes/default/counter-redis
Generate a deploy file manifests/default/counter/Pod/counter.yml of the Pod type:
Generate a service file manifests/default/counter/Pod/Service/counter.yml of the Pod type
```

*If there is no need to output generation steps, the `-v` flag can be omitted.*

The first parameter `pod_counter` specifies the name of the raised `podman-POD`.
The second `docker-compose.yaml` is the name of the YAML file from which it is started
containers.

After calling the command, a subdirectory `manifests` will be created in the current directory with
following structure:
```
manifests/
└── default
    └── counter
        └── Pod
            ├── counter.yml
            ├── Service
            │   └── counter.yml
            ├── PersistentVolumeClaim
            │   └── counter-redis.yml
            └── PersistentVolume
                └── default-counter-redis.yml
```
At the first level, a directory `default` will be created whose name specifies
`kubernetes-namespace` in which `POD` will be launched.

In the `default` subdirectory, a `counter` subdirectory is created whose name is
is taken from the name of the generated `POD` by discarding the `pod_` prefix.

In the `counter` subdirectory, a subdirectory is created by the name of the expansion -
`Pod`.

In the deployment type directory `Pod` the following are generated:

- Pod container description file `counter.yml`;
- subdirectory of the description of the kubernet service `Service`
- subdirectory `PersistentVolumeClaim` description of the kubernet request for
     mounted volumes
- subdirectory `PersistentVolume` description of volumes for a given
     deployment.

##### Pod container description file counter.yml

The Pod container description file `counter.yml` looks like this:
```
# Created with podman-compose-to-kube 1.0.0-alt1
apiVersion: v1
kind: Pod
metadata:
  creationTimestamp: '2024-01-27T11:05:26Z'
  labels:
    app: counter
  name: counter
  namespace: default
spec:
  containers:
    - args:
        - redis-server
        - --appendonly
        - 'yes'
        - --notify-keyspace-events
        - Ex
      image: docker.io/library/redis:alpine
      name: counterredis1
      ports:
        - containerPort: 6379
      securityContext:
        readOnlyRootFilesystem: true
      volumeMounts:
        - mountPath: /data
          name: counter-redis-pvc
    - env:
        - name: REDIS_HOST
          value: redis
        - name: REDIS_PORT
          value: '6379'
      image: localhost/hello-py-aioweb:latest
      name: counterweb1
      ports:
        - containerPort: 8080
      securityContext:
        readOnlyRootFilesystem: true
  volumes:
    - name: counter-redis-pvc
      persistentVolumeClaim:
        claimName: counter-redis
  hostAliases:
    - ip: 127.0.0.1
      hostnames:
        - redis
        - web
```

The file describes in `namespace: default` in a POD named `counter` two
container: `counterredis1`, `counterweb1`.

The container `counterredis1` accepts requests on port `6379` and mounts
the `/data` directory on the volume obtained by request (`PersisnentVolumeClaim`)
with name (`claimName`) `counter-redis`.

The `counterweb1` container accepts requests on port `8080`. On his environment
two variables are exported: `REDIS_HOST` and `REDIS_PORT`.

Since in a `POD` type deployment both containers start in the same
`POD` with local address `127.0.0.1` is added to the YML file
description of `hostAliases`, binding short DNS names `web`, `redis`
to local address `127.0.0.1`. Thus the `redis` container
accessible from the `web` container under the name `redis` via local
interface `lo` `POD`.

##### Subdirectory for the description of the kubernet service Service

Since only one `POD` subdirectory is launched as part of the deployment
descriptions of the kubernet service `Service` contains only one file
`counter.yml`:
```
# Created with podman-compose-to-kube 1.0.0-alt1
apiVersion: v1
kind: Service
metadata:
  creationTimestamp: '2024-01-27T11:05:26Z'
  labels:
    app: counter
  name: counter
  namespace: default
spec:
  ports:
    - name: '6379'
      nodePort: 32717
      port: 6379
      targetPort: 6379
    - name: '8080'
      nodePort: 31703
      port: 8080
      targetPort: 8080
  selector:
    app: counter
  type: NodePort
```

The file describes for a `POD` named `counter` in `namespace: default`
two ports for external access:

- `6379` - with a node port for external access `32717`;
- `8080` - with a node port for external access `31703`.

If external access to the container `counterredis1` does not require a description
port `6379` can be removed.

##### Subdirectory PersistentVolumeClaim description of the kubernet request for mounted volumes

`docker-compose` YML file contains a description of only one outer volume
for the `redis` service. This description generates an allocation request
volumes contained in the `counter-redis.yml` file:
```
# Created with podman-compose-to-kube 1.0.6-alt1
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  annotations:
    volume.podman.io/driver: local
  creationTimestamp: '2024-01-27T11:05:27Z'
  name: counter-redis
  namespace: default
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: manual
```
File for request `counter-redis` in `namespace:default` requests volume
volume `1Gi`.

##### Subdirectory `PersistentVolume` description of volumes for this deployment

For each request for a volume in the `PersistentVolume` directory, a
description of the volume on the host's local disk. File `default-counter-redis.yml`
contains the following information:
```
# Created with podman-compose-to-kube 1.0.6-alt1
apiVersion: v1
kind: PersistentVolume
metadata:
  name: default-counter-redis
  labels:
    type: local
spec:
  storageClassName: manual
  claimRef:
    name: counter-redis
    namespace: default
  capacity:
    storage: 1Gi
  accessModes:
    - ReadWriteOnce
  hostPath:
    path: /mnt/PersistentVolumes/default/counter-redis
```
For a request (`claimRef`) named `counter-redis` in the directory
`/mnt/PersistentVolumes/default/counter-redis` is allocated `1Gi`
disk space. Volume root directory name
`/mnt/PersistentVolumes/` can be changed by specifying a different directory in
parameter `--pvpath`.

#### Running POD manifests

`POD manifests` are launched with the command:
```
kubectl apply -R -f manifests/default/counter/Pod/

persistentvolume/default-counter-redis created
persistentvolumeclaim/counter-redis created
service/counter created
pod/counter created
```
Command recursively execute all YML files of a directory
`manifests/default/counter/Pod/`.

The state of the container and service can be viewed with the command:
```
kubectl -n default get all -o wide

NAME            READY   STATUS    RESTARTS      AGE     IP            NODE     NOMINATED NODE   READINESS GATES
pod/counter     2/2     Running   0             22m     10.88.0.99    host-8   <none>           <none>

NAME                 TYPE        CLUSTER-IP    EXTERNAL-IP   PORT(S)                         AGE   SELECTOR
service/counter      NodePort    10.108.81.8   <none>        6379:30031/TCP,8080:30748/TCP   22m   app=counter
```
Check the outer volume assignment:
```
kubectl -n default get pvc

NAME            STATUS   VOLUME                  CAPACITY   ACCESS MODES   STORAGECLASS   AGE
counter-redis   Bound    default-counter-redis   1Gi        RWO            manual         46s
```

##### Checking POD Operation

To check the operation of the POD, run the container from the image
`praqma/network-multitool`:
```
kubectl run multitool --image=praqma/network-multitool

pod/multitool created
```

Make a request to the `counter.default` service from the container:
```
kubectl exec -it pod/multitool -- curl http://counter.default:8080

counter=1
```
Operation can also be checked by accessing the external port of the node, on
which `POD` is running:

```
curl http://<IP>:30748

counter=2
```

#### Stopping POD manifests

To stop the POD, type the command:
```
kubectl delete -R -f manifests/default/counter/Pod/

persistentvolume "default-counter-redis" deleted
persistentvolumeclaim "counter-redis" deleted
service "counter" deleted
pod "counter" deleted
```

### Deployment as kubernetes Deployment

#### Manifest generation

Manifests for Deployment deployment are generated by
command:
```
podman-compose-to-kube -t d -v pod_counter docker-compose.yaml
```

*If the output of generation steps is not necessary, the `-v` flag can be omitted.*

The format for calling the command to generate Deployment deployment is different
the presence of the `-t d` flag (`--type=deployment`).
```
Generate a POD manifest based on the specified POD
Replace symbols _ to - in yml elements ending with name(Name)
Generate list of services in docker-compose file
Get descriptions of the environment variables
Generate common POD file
Generate PersistentVolumeClaims and PersistentVolumes:
        t/default/counter/Pod/PersistentVolumeClaim/counter-redis.yml
        t/default/counter/Pod/PersistentVolume/default-counter-redis.yml
        /mnt/PersistentVolumes/default/counter-redis
Generate a deploy file t/default/counter/Pod/counter.yml of the Pod type:
Generate a service file t/default/counter/Pod/Service/counter.yml of the Pod type
```

After calling the command, a subdirectory `manifests` will be created in the current directory
following structure:
```
manifests/
└── default
    └── counter
        └── Deployment
            ├── redis.yml
            ├── web.yml
            ├── Service
            │   ├── redis.yml
            │   └── web.yml
            ├── PersistentVolumeClaim
            │   └── counter-redis.yml
            └── PersistentVolume
                └── default-counter-redis.yml
```

##### Description files for the Deployment solution redis.yml, web.yml

Deployment solution description files are placed in the `Deployment` subdirectory
`counter` directory. Since during Deployment deployment each
the container can be replicated, they are placed in different Deployment's,
described in the YML files `redis.yml`, `web.yml`.

Deploying the `redis` service, file `redis.yml`:
```
# Created with podman-compose-to-kube 1.0.6-alt1
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  labels:
    app: redis
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - args:
            - redis-server
            - --appendonly
            - 'yes'
            - --notify-keyspace-events
            - Ex
          image: docker.io/library/redis:alpine
          name: counterredis1
          ports:
            - containerPort: 6379
          securityContext:
            readOnlyRootFilesystem: true
          volumeMounts:
            - mountPath: /data
              name: counter-redis-pvc
      volumes:
        - name: counter-redis-pvc
          persistentVolumeClaim:
            claimName: counter-redis
```

The container description in the `spec.template.spec` element matches
description in POD mode in the zero element `spec`, like the element
descriptions of the external volume `spec.template.volumes`. Since the container
has an external volume mounted in read-write mode this
container cannot replicate: `spec.replicas: 1`.

Deploying the `web` service, file `web.yml`:
```
# Created with podman-compose-to-kube 1.0.6-alt1
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  labels:
    app: web
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
        - env:
            - name: REDIS_HOST
              value: redis
            - name: REDIS_PORT
              value: '6379'
          image: localhost/hello-py-aioweb:latest
          name: counterweb1
          ports:
            - containerPort: 8080
          securityContext:
            readOnlyRootFilesystem: true
```
As for the `redis` service in the `web` service, the description of the container in the element
`spec.template.spec` matches the description in POD mode in the first
element `spec`. Since the container does not have external volumes, this container
can be replicated to required values.
The required number of replicas is specified in the `spec.replicas` element.

##### Subdirectory for the description of the kubernet service `Service`

Since during Deployment mode the containers are deployed in
separate POD's and both have ports, then for each of them are generated
separate service description files `Service/redis.yml`, `Service/web.yml`.

File `redis.yml` describe the `redis` service:
```
# Created with podman-compose-to-kube 1.0.6-alt1
apiVersion: v1
kind: Service
metadata:
  creationTimestamp: '2024-01-27T16:04:24Z'
  labels:
    app: redis
  name: redis
  namespace: default
spec:
  ports:
    - name: '6379'
      nodePort: 30921
      port: 6379
      targetPort: 6379
  selector:
    app: redis
  type: NodePort
```

If the service `Service/web.yml` does not need to be accessed from outside
the `spec.ports[0].nodePort` element can be removed.

File `web.yml` describe the `web` service:
```
# Created with podman-compose-to-kube 1.0.6-alt1
apiVersion: v1
kind: Service
metadata:
  creationTimestamp: '2024-01-27T16:04:24Z'
  labels:
    app: web
  name: web
  namespace: default
spec:
  ports:
    - name: '8080'
      nodePort: 31434
      port: 8080
      targetPort: 8080
  selector:
    app: web
  type: NodePort
```

##### Subdirectories PersistentVolumeClaim, PersistentVolume

Structure and contents of subdirectories `PersistentVolumeClaim`, `PersistentVolume`
The `Deployment` deployment is the same as the `Pod` deployment described
above&deg;&deg;&deg;.

#### Running deployment manifests

The `Deployment manifests` are launched with the command:
```
kubectl apply -R -f manifests/default/counter/Deployment/

persistentvolume/default-counter-redis created
persistentvolumeclaim/counter-redis created
service/redis created
service/web created
deployment.apps/redis created
deployment.apps/web created
```

The command will recursively execute all YML files of the directory
`manifests/default/counter/Deployment/`.

If necessary, you can replicate (for example, in the amount of 3)
Deployment web command:
```
kubectl scale --replicas=3 deployment web
```

The state of containers and services can be viewed with the command:
```
kubectl -n default get all -o wide

NAME                         READY   STATUS    RESTARTS      AGE     IP            NODE     NOMINATED NODE   READINESS GATES
pod/redis-7595cd897c-894dd   1/1     Running   0             3m46s   10.88.0.103   host-8   <none>           <none>
pod/web-5778c5c-b8gcw        1/1     Running   0             3m46s   10.88.0.102   host-8   <none>           <none>
pod/web-5778c5c-h7bjh        1/1     Running   0             7s      10.88.0.104   host-8   <none>           <none>
pod/web-5778c5c-nqxhs        1/1     Running   0             7s      10.88.0.105   host-8   <none>           <none>

NAME                 TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE     SELECTOR
service/redis        NodePort    10.110.219.99   <none>        6379:30921/TCP   3m46s   app=redis
service/web          NodePort    10.103.86.45    <none>        8080:31434/TCP   3m46s   app=web

NAME                    READY   UP-TO-DATE   AVAILABLE   AGE     CONTAINERS      IMAGES                             SELECTOR
deployment.apps/redis   1/1     1            1           3m46s   counterredis1   docker.io/library/redis:alpine     app=redis
deployment.apps/web     3/3     3            3           3m46s   counterweb1     localhost/hello-py-aioweb:latest   app=web

NAME                               DESIRED   CURRENT   READY   AGE     CONTAINERS      IMAGES                             SELECTOR
replicaset.apps/redis-7595cd897c   1         1         1       3m46s   counterredis1   docker.io/library/redis:alpine     app=redis,pod-template-hash=7595cd897c
replicaset.apps/web-5778c5c        3         3         3       3m46s   counterweb1     localhost/hello-py-aioweb:latest   app=web,pod-template-hash=5778c5c
```

Check the outer volume assignment:
```
kubectl -n default get pvc

NAME            STATUS   VOLUME                  CAPACITY   ACCESS MODES   STORAGECLASS   AGE
counter-redis   Bound    default-counter-redis   1Gi        RWO            manual         46s
```

#### Checking the Deploymant's operation

To check the operation of the POD, run (if you have not done so before)
container from the `praqma/network-multitool` image:
```
kubectl run multitool --image=praqma/network-multitool

pod/multitool created
```
Make a request to the `web.default` service from the container:
```
kubectl exec -it pod/multitool -- curl http://web.default:8080

counter=3
```
*Please note that unlike deploying a Pod (domain
`counter.default`) the domain `web.default` is being accessed.*

Operation can also be checked by accessing the external port of the node, on
which `POD` is running:
```
curl http://<IP>:31434

counter=4
```

#### Stopping Deployment manifests

To stop the POD, type the command:
```
kubectl delete -R -f manifests/default/counter/Deployment/

persistentvolume "default-counter-redis" deleted
persistentvolumeclaim "counter-redis" deleted
service "redis" deleted
service "web" deleted
deployment.apps "redis" deleted
deployment.apps "web" deleted
```

## Features of deployment in a rootless environment

> This section describes running the generated manifests in a `rootless environment`, formed as part of the [podsec package](https://github.com/alt-cloud/podsec)

### Specifying a username when generating manifests

When generating for rootless-kubernetes, specify when calling the command
`podman-compose-to-kube` username flag `-u` (`--user`) name
the user under which `kubernetes` runs (and the group name with the `-n` flag
(`--group`) if the group name is different from the user name).
For example, if `kubernetes` is running under the user `u7s-admin`
the `Deployment-deployment` generation command looks like this:
```
podman-compose-to-kube -u u7s-admin -t d pod_counter docker-compose.yaml
```

When specifying the `-u` flag for those created on the local file system
volumes as owners are set to those specified in the parameters
user and group.

### Copying local images in a rootless environment

In a rootless environment, images created by `podman-compose` are stored in
directory `/var/lib/u7s-admin/.local/share/containers/storage/`. Images
for kubernetes they are stored in a different directory
`/var/lib/u7s-admin/.local/share/usernetes/containers/storage/`. For
images downloaded from registrars is unimportant, since they
are loaded when `POD`\' is launched. Images created locally, as in
In our case, the image `localhost/hello-py-aioweb` needs to be transferred to
`container-storage` for kubernetes images using the `skopeo` command:
```
# skopeo copy \
  containers-storage:[/var/lib/u7s-admin/.local/share/containers/storage/]localhost/hello-py-aioweb \
  containers-storage:[/var/lib/u7s-admin/.local/share/usernetes/containers/storage/]localhost/hello-py-aioweb
```
and change the owner of the transferred image from `root` to `u7s-admin`:
```
# chown -R u7s-admin:u7s-admin /var/lib/u7s-admin/.local/
```

### Forwarding external ports on the node

In `rootless mode` all created Nodeport ports remain in the namespace
the user under which `kubernetes` is running. For port forwarding
outside you need to go to the user's `namepspace` with the command:
```
machinectl shell u7s-admin@ /usr/libexec/podsec/u7s/bin/nsenter_u7s

[INFO] Entering RootlessKit namespaces: OK
[root@host ~]#
```
and do port forwarding:
```
# rootlessctl \
  --socket /run/user/989/usernetes/rootlesskit/api.sock
  add-ports "0.0.0.0:30748:30748/tcp"

10
```

Where:

- `989` - identifier (`uid`) of the user `u7s-admin`;

- `30748` - number of the forwarded port.
