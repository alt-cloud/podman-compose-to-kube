# podman-compose-to-kube — инструмент миграции решений docker-compose в kubernetes

Одной из основных проблем миграции `docker-compose` (`docker swarm`)
решений в `kubernetes` является генерация `kubernetes-манифестов` из
`YAML-файлов описания стека сервисов`. Существует достаточно бедный
набор инструментов, решающий данную проблему. Данный документ описывает
решение данной проблемы путем использования команд
[podman-compose](https://github.com/containers/podman-compose),
[podman-compose-to-kube](https://github.com/alt-cloud/podman-compose-to-kube).

В качестве примера разворачивания стека использован
`docker-compose` стек
[hello-python](https://github.com/containers/podman-compose/tree/devel/examples/hello-python)
проекта `podman-compose`.

Описаны варианты разворачивания миграции как `rootfull` так и
`rootless-решений`.

## Разворачивание docker-compose стека в podman-compose

### Загрузка описания стека сервисов hello-python

Скопируйте содержимое каталога
[hello-python](https://github.com/containers/podman-compose/tree/devel/examples/hello-python).

Если у Вас установлен git это можно сделать командами:
```
# git clone -n --depth=1 --filter=tree:0 https://github.com/containers/podman-compose.git
# cd podman-compose/
# git sparse-checkout set --no-cone examples/hello-python
# git checkout
```
После выполнения команд в каталоге
`podman-compose/examples/hello-python` развернется содержание указанного
выше каталога.

### Разворачивание стека сервисов

#### Описание стека сервисов

Перейдите в каталог `podman-compose/examples/hello-python`. В каталоге
присутствует файл `docker-compose.yml` описание стека сервисов:
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

В сервисе `redis` запускается контейнер с томом `redis` и портом для
внешнего доступа `6379`.

В сервисе `web` собирается образ `hello-py-aioweb`.
Образу присваивается  имя `localhost/hello-py-aioweb`.
На его основе создается контейнер, поддерживающий прием HTTP-запросов по порту `8080`.
Образ `localhost/hello-py-aioweb` собирается на основе `Dockerfile`:
```
FROM python:3.9-alpine

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "-m", "app.web" ]
EXPOSE 8080
```

При запуске контейнера запускается python-скрипт `app/web.py`.
Скрипт принимает HTTP-запросы и формирует счетчик запросов в redis-базе.
В качестве ответа возвращается текст с номером запроса в базе.

#### Запуск стека сервисов

Перед запуском стека сервисов необходимо уточнить файл
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
В файл внесены два изменения:

1.  В сервис `redis` добавлено описание порта `6379`.
2.  В сервис `web` добавлено описание переменной `REDIS_PORT: 6379`.

Оба эти изменения необходимы при разворачивании kubernet-сервисов в
режиме `Deployment`.

Первое изменения связано с тем, что если описание порта отсутствует, то
при генерации из за отсутствия информации не сгенерируется
`YML-файл описания kubernet-сервиса` и `redis-контейнер` будет
недоступен из контейнера `web`.

Второе изменение связано с тем, что в режиме `Deployment` в контейнер
`web` экпортируется переменная `REDIS_PORT` в формате
`http://<ip>:<port>`. Приложение `App/web.py`
обрабатывает это значение в формате `<port>`.

Для запуска стека сервисов наберите команду:
```
podman-compose --in-pod counter -p counter up -d
```

*При использовании `podman-compose` версии `>= 1.0.7` параметр
`--in-pod` необязателен.*

Параметр `-p` задает имя проекта - суффикс имени `POD`\'а
(`pod_counter`) и префикс имен контейнеров и томов. Если параметр `-p`
отсутствует в качестве имени проекта принимается имя текущего каталога
(в нашем случае `hello-python`).

В процессе работы `podman-compose` выводит список запускаемых команд:
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

После запуска POD\'а и контейнеров состояние можно посмотреть командами:
- список запущенных POD\'ов:
```
podman pod ls

POD ID        NAME         STATUS      CREATED        INFRA ID    # OF CONTAINERS
d37ba3addeb3  pod_counter  Running     9 minutes ago              2
```

-   Логи контейнеров POD\'а:

```
podman pod logs pod_counter

b5bdc8d1977f 1:C 18 Jan 2024 11:04:20.309 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
...
b5bdc8d1977f 1:M 18 Jan 2024 11:04:20.312 * Ready to accept connections tcp
```

-   Список запущенных контейнеров:

```
podman ps

CONTAINER ID  IMAGE                             COMMAND               CREATED         STATUS         PORTS                   NAMES
...
b5bdc8d1977f  docker.io/library/redis:alpine    redis-server --ap...  27 minutes ago  Up 27 minutes                          counter_redis_1
49f6f5141b24  localhost/hello-py-aioweb:latest  python -m App.web     27 minutes ago  Up 27 minutes  0.0.0.0:8080->8080/tcp  counter_web_1
...
```

-   Логи контейнера базы данных redis

```
podman logs counter_redis_1

1:C 18 Jan 2024 11:04:20.309 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
...
1:M 18 Jan 2024 11:04:20.312 * Ready to accept connections tcp
```

-   Логи контейнера WEB-интерфейса web:

```
podman log counter_web_1
```

### Проверка работы стека сервисов

Для проверки работы стека последовательно пошлите запросы командой curl
на порт 8080:
```
# curl localhost:8080/
counter=1
# curl localhost:8080/
counter=2
# curl localhost:8080/
counter=3
...
```

## Экспорт запущенного POD\'а в kubernetes-манифесты и их запуск

### Разворачивание в виде kubernetes POD

Генерация манифестов производится командой `podman-compose-to-kube`.
Формат ее вызова:
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

#### Генерация манифестов

Генерация манифестов для POD-разворачивания производится командой:
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

*Если в выводе шагов генерации нет необходимости флаг `--v` можно опустить.*

Первый параметр `pod_counter` указывает имя поднятого `podman-POD`.
Второй `docker-compose.yaml` - имя YAML-файла из которого запущены контейнеры.

После вызова команды в текущем каталоге создастся подкаталог `manifests`
следующей структуры:
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

На первом уровне создастся каталог `default` имя которого задает
`kubernetes-namespace` в котором будет запускаться `POD`.

В подкаталоге `default` создается подкаталог `counter` имя которого
берется из имени генерируемого `POD`\'а отбрасыванием префикса `pod_`.

В подкаталоге `counter` создается подкаталог по имени разворачивания -
`Pod`.

В каталоге типа разворачивания `Pod` генерируются:

-   файл описания Pod-контейнера `counter.yml`;
-   подкаталог описания kubernet-сервиса `Service`
-   подкаталог `PersistentVolumeClaim` описания kubernet-запроса на
    монтируемые тома
-   подкаталог `PersistentVolume` описания томов для данного
    разворачивания.

##### Файл описания Pod-контейнера counter.yml

Файл описания Pod-контейнера `counter.yml` выглядит следующим образом:
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

Файл описывает в `namespace: default` в POD\'е с именем `counter` два
контейнера: `counterredis1`, `counterweb1`.

Контейнер `counterredis1` принимает запросы по порту `6379` и монтирует
каталог `/data` на том, получаемый по запросу (`PersisnentVolumeClaim`)
с именем (`claimName`) `counter-redis`.

Контейнер `counterweb1` принимает запросы по порту `8080`. В его среду
экспортируются две переменные: `REDIS_HOST` и `REDIS_PORT`.

Так как в разворачивании типа `POD` оба контейнера стартуют в одном
`POD`\'е с локальным адресом `127.0.0.1`, к YML-файлу добавляется
описание `hostAliases`, привязывающий короткие DNS-имена `web`, `redis`
к локальному адресу `127.0.0.1`. Таким образом контейнер `redis`
доступен из контейнера `web` под именем `redis` через локальный
интерфейс `lo` `POD`\'а.

##### Подкаталог описания kubernet-сервиса `Service`

Так как в рамках разворачивания запускается всего один `POD` подкаталог
описания kubernet-сервиса `Service` содержит всего один файл
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

Файл описывает для `POD`\'а с именем `counter` в `namespace: default`
два порта для внешнего доступа:

-   `6379` - с node-портом для внешнего доступа `32717`;
-   `8080` - с node-портом для внешнего доступа `31703`.

Если внешний доступ к контейнеру `counterredis1` не требуется описание
порта `6379` можно удалить.

##### Подкаталог `PersistentVolumeClaim` описания kubernet-запроса на монтируемые тома

docker-compose YML файл содержит описание только одного внешнего тома
для сервиса `redis`. Данное описание генерирует запрос на выделение
тома, содержащееся в файле `counter-redis.yml`:
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

Файл для запроса `counter-redis` в `namespace: default` запрашивает том
объемом `1Gi`.

##### Подкаталог `PersistentVolume` описания томов для данного разворачивания

Для каждого запроса на том в каталоге `PersistentVolume` формируется
описание тома на локальном диске узла. Файл `default-counter-redis.yml`
содержит следующую информацию:
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
Для запроса (`claimRef`) с именем `counter-redis` в каталоге
`/mnt/PersistentVolumes/default/counter-redis` выделяется `1Gi`
дискового пространства. Имя корневого каталог томов
`/mnt/PersistentVolumes/` можно изменить указав друглй каталог в
параметре `--pvpath`.

#### Запуск манифестов POD

Запуск `POD-манифестов` производится командой:
```
kubectl apply -R -f manifests/default/counter/Pod/

persistentvolume/default-counter-redis created
persistentvolumeclaim/counter-redis created
service/counter created
pod/counter created
```
Команда рекурсивно выполнить все YML-файлы каталога
`manifests/default/counter/Pod/`.

Состояние контейнера и сервиса можно посмотреть командой
```
kubectl -n default get all -o wide

NAME            READY   STATUS    RESTARTS      AGE     IP            NODE     NOMINATED NODE   READINESS GATES
pod/counter     2/2     Running   0             22m     10.88.0.99    host-8   <none>           <none>

NAME                 TYPE        CLUSTER-IP    EXTERNAL-IP   PORT(S)                         AGE   SELECTOR
service/counter      NodePort    10.108.81.8   <none>        6379:30031/TCP,8080:30748/TCP   22m   app=counter
```
Проверьте назначение внешнего тома:
```
kubectl -n default get pvc

NAME            STATUS   VOLUME                  CAPACITY   ACCESS MODES   STORAGECLASS   AGE
counter-redis   Bound    default-counter-redis   1Gi        RWO            manual         46s
```

#### Проверка работы POD

Для проверки работы POD\'а запустите контейнер от образа
`praqma/network-multitool`:
```
kubectl run multitool --image=praqma/network-multitool

pod/multitool created
```

Сделайте запрос на сервис `counter.default` из конейнера:
```
kubectl exec -it pod/multitool -- curl http://counter.default:8080

counter=1
```
Работу можно проверить также обратившись к внешнему порту узла, на
котором запущен `POD`:
```
curl http://<IP>:30748

counter=2
```

#### Останов манифестов POD\'а

Для остановки работы POD\'а наберите команду:
```
kubectl delete -R -f manifests/default/counter/Pod/

persistentvolume "default-counter-redis" deleted
persistentvolumeclaim "counter-redis" deleted
service "counter" deleted
pod "counter" deleted
```

### Разворачивание в виде kubernetes Deployment

##### Генерация манифестов

Генерация манифестов для Deployment-разворачивания производится
командой:
```
podman-compose-to-kube -t d -v pod_counter docker-compose.yaml
```

*Если в выводе шагов генерации нет необходимости флаг `-v` можно
опустить.*

Формат вызова команды для генерации Deployment-разворачивания отличается
наличием флага `-t d` (`--type=deployment`).
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

После вызова команды в текущем каталоге создастся подкаталог `manifests`
следующей структуры:
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

##### Файлы описания Deployment-решения redis.yml, web.yml

Файлы описания Deployment-решения помещаются в подкаталог `Deployment`
каталога `counter`. Так как при Deployment-разворачивании каждый
контейнер может реплицироваться они помещаются в разные Deployment\'s,
описываемые в YML-файлах `redis.yml`, `web.yml`.

Разворачивание сервиса `redis`, файл `redis.yml`:
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

Описание контейнера в элементе `spec.template.spec` совпадает с
описанием в режиме POD\'а в нулевом элементе `spec`, как и элемент
описания внешнего тома `spec.template.volumes`. Так как контейнер
имеет внешний том, примонтированный в режиме чтения-записи этот
контейнер не может реплицироваться: `spec.replicas: 1`.

Разворачивание сервиса `web`, файл `web.yml`:
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

Как и для сервиса `redis` в сервисе `web` описание контейнера в элементе
`spec.template.spec` совпадает с описанием в режиме POD\'а в первом
элементе `spec`. Так как контейнер не имеет внешних томов этот контейнер
может реплицироваться до требуемых значений.
Требуемое число реплик указывается в элементе `spec.replicas`.

##### Подкаталог описания kubernet-сервиса `Service`

Так как в Deployment-режиме контейнеры разворачиваются в
отдельных POD\'ах и оба имеют порты, то для каждого из них генерируются
отдельных файлах описания сервисов `Service/redis.yml`, `Service/web.yml`.

Файл `redis.yml` описания сервиса `redis`:
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

Если к сервису `Service/web.yml` не необходимости обращении извне
элемент `spec.ports[0].nodePort` можно удалить.

Файл `web.yml` описания сервиса `web`:
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

##### Подкаталоги `PersistentVolumeClaim`, `PersistentVolume`

Структура и содержание подкаталогов `PersistentVolumeClaim`, `PersistentVolume`
разворачивания `Deployment` совпадает с разворачиванием `Pod`, описанное
выше.

#### Запуск Deployment-манифестов

Запуск `Deployment-манифестов` производится командой:
```
kubectl apply -R -f manifests/default/counter/Deployment/

persistentvolume/default-counter-redis created
persistentvolumeclaim/counter-redis created
service/redis created
service/web created
deployment.apps/redis created
deployment.apps/web created
```

Команда рекурсивно выполнит все YML-файлы каталога
`manifests/default/counter/Deployment/`.

При необходимости Вы можете реплицировать (например в количестве 3)
Deployment web командой:
```
kubectl scale --replicas=3 deployment web
```

Состояние контейнеров и сервисов можно посмотреть командой
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

Проверьте назначение внешнего тома:
```
kubectl -n default get pvc

NAME            STATUS   VOLUME                  CAPACITY   ACCESS MODES   STORAGECLASS   AGE
counter-redis   Bound    default-counter-redis   1Gi        RWO            manual         46s
```

### Проверка работы Deployment

Для проверки работы POD\'а запустите (если не сделали это ранее)
контейнер от образа `praqma/network-multitool`:
```
kubectl run multitool --image=praqma/network-multitool

pod/multitool created
```

Сделайте запрос на сервис `web.default` из конейнера:
```
kubectl exec -it pod/multitool -- curl http://web.default:8080

counter=3
```

*Обратите внимание, что в отличие от разворачивания Pod (домен
`counter.default`) идет обращение к домену `web.default`.*

Работу можно проверить также обратившись к внешнему порту узла, на
котором запущен `POD`:
```
curl http://<IP>:31434

counter=4
```

#### Останов манифестов Deployment\'а

Для остановки работы POD\'а наберите команду:
```
kubectl delete -R -f manifests/default/counter/Deployment/
```
```
persistentvolume "default-counter-redis" deleted
persistentvolumeclaim "counter-redis" deleted
service "redis" deleted
service "web" deleted
deployment.apps "redis" deleted
deployment.apps "web" deleted
```

## Особенности запуска в rootless окружении

> Данный раздел описывает запуск сгенерированных манифестов в `rootless окружении`, сформированного в рамках пакета [podsec](https://github.com/alt-cloud/podsec)

### Указание имени пользователя при генерации манифестов

При генерации для rootless-kubernetes укажите при вызове команды
`podman-compose-to-kube` имя пользователя флагом `-u` (`--user`) имя
пользователя под которым работает `kubernetes` (и имя группы флагом `-п`
(`--group`), если имя группа отличается от имени пользователя).
Например, если `kubernetes` работает под пользователем `u7s-admin`
команда генерации `Deployment-разворачивания` выглядит так:
```
podman-compose-to-kube -u u7s-admin -t d pod_counter docker-compose.yaml
```

При указании флага `-u` для создаваемых в локальной файловой системе
томов в качестве владельцев устанавливаются указанные в параметрах
пользователь и группа.

### Копирование локальных образов в rootless окружении

В rootless-окружении образы, созданные `podman-compose` хранятся в
каталоге `/var/lib/u7s-admin/.local/share/containers/storage/`. Образы
же для kubernetes хранятся в другом каталоге
`/var/lib/u7s-admin/.local/share/usernetes/containers/storage/`. Для
образов, загружаемых с регистраторов это несущественно, так как они
подгружаются при запуске `POD`\'а. Образы же, созданные локально, как в
нашем случае образ `localhost/hello-py-aioweb` необходимо перенести в
`container-storage` для kubernetes-образов командой `skopeo`:
```
# skopeo copy \
  containers-storage:[/var/lib/u7s-admin/.local/share/containers/storage/]localhost/hello-py-aioweb \
  containers-storage:[/var/lib/u7s-admin/.local/share/usernetes/containers/storage/]localhost/hello-py-aioweb
```
и изменить собственника перенесенного образа с `root` на `u7s-admin`:
```
# chown -R u7s-admin:u7s-admin /var/lib/u7s-admin/.local/
```

### Проброс внешних портов на узле

В `rootless-режиме` все создаваемые Nodeport-порты остаются в namespace
пользователя от имени которого запущен `kubernetes`. Для проброса портов
наружу необходимо зайти в `namepspace` пользователя командой:
```
machinectl shell u7s-admin@ /usr/libexec/podsec/u7s/bin/nsenter_u7s

[INFO] Entering RootlessKit namespaces: OK
[root@host ~]#
```
и сделать проброс портов:
```
# rootlessctl \
  --socket /run/user/989/usernetes/rootlesskit/api.sock
  add-ports "0.0.0.0:30748:30748/tcp"

10
```
Где:

-   `989` - идентификатор (uid) пользователя `u7s-admin`;

-   `30748` - номер пробрасываемого порта.
