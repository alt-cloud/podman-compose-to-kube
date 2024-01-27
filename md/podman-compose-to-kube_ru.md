podman-compose-to-kube(1) -- генерации kubernetes манифестов на основе поднятого podman-compose POD'а
================================

## SYNOPSIS
<pre>
podman-compose-to-kube \
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

Скрипт поддержки миграции решений docker-compose в kubernetes.

До вызова скрипта необходимо с помощью команды podman-compose поднять  стек сервисов в POD'е и проверить его работоспособность (см. [podman-compose как средство миграция docker-compose решений в kubernetes](https://www.altlinux.org/Podman-compose/kubernetes#%D0%AD%D0%BA%D1%81%D0%BF%D0%BE%D1%80%D1%82_%D1%80%D0%B0%D0%B7%D0%B2%D0%B5%D1%80%D0%BD%D1%83%D1%82%D0%BE%D0%B3%D0%BE_%D1%81%D1%82%D0%B5%D0%BA%D0%B0_%D0%B2_kubernetes-%D0%BC%D0%B0%D0%BD%D0%B8%D1%84%D0%B5%D1%81%D1%82%D1%8B)).

Скрипт podman-compose-to-kube генерирует манифесты Kubernetes для развертывания указанного стека сервисов.
в `kubernetes`.
В качестве основы для генерации используется `POD`, созданный командой `podman-compose`.

Манифесты генерируются в каталоге, указанном параметром `--dir` (`-d`) (по умолчания каталог `manifests`).
Каталог манифестов имеет следующую структуру:
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

Каталог манифестов (по умолчанию `manifests`) содержит подкаталоги `namespace`ов.

В рамках каталога `namespace` для каждого генерируемого набора манифестов создается отдельный каталог для каждого `Pod`'а.
Имя каталога формируется из имени `Pod`'а путем удаления префикса `pod`.

В каталоге `Pod`'а для каждого типа разворачивания (`Pod`, `Deployment`) создается подкаталог, содержащий YML-файлы манифестов:

- файлы манифестов `*.yml` - файлы разворачивания контейнеров  (`kind: Pod`, `kind: Deployment`);
- каталог `Service` с YML-файлами описания сервисов (`kind: Service`);
- каталог `PersistentVolumeClaim` с YML-файлами описания запросов на внешние тома (`kind: PersistentVolumeClaim`);
- каталог `PersistentVolume` с YML-файлами описания описание внешних локальных томов (`kind: PersistentVolume`).

Файлы  каталога `PersistentVolume` описания описание внешних локальных томов имеют ссылки на соответствующие файлы YML- описания запросов на внешние тома каталога `PersistentVolumeClaim`.

Данный формат размещения YML-файлов манифестов позволяет разворачивать kubernetes-решение одной командой:
<pre>
kubectl apply -R -f manifests/&lt;namespace1>/&lt;podName>/Pod
</pre>
для POD-разворачивания или
<pre>
kubectl apply -R -f manifests/&lt;namespace1>/&lt;podName>/Deployment
</pre>
для Deployment-разворачивания.
<br>
<br>
А также удалять разворачивание:
<pre>
kubectl delete -R -f manifests/&lt;namespace1>/&lt;podName>/Pod
</pre>
для POD-разворачивания или
<pre>
kubectl delete -R -f manifests/&lt;namespace1>/&lt;podName>/Deployment
</pre>
для Deployment-разворачивания.


### Тип разворачивания POD

**Deploy-файл типа Pod (kind: Pod)**


При типе разворачивания `POD` (`--type pod` или `-t p`) в каталоге `manifests/<namespace>/<podName>/Pod/`
генерируется YML-файл разворачивания (`kind: Pod`) `<pod1Name>.yml`.

Все контейнеры `docker-compose сервисов` запускаются в рамках одного пода.
Сетевое взаимодействипе между контейнерами одного стека сервисов осуществляется через интерфейс localhost (127.0.0.1).
В связи  с этим в YML-файл добавляется описание:
<pre>
  hostAliases:
    - ip: 127.0.0.1
      hostnames:
        - &lt;имя_сервиса1>
        - &lt;имя_сервиса2>
        - ...
</pre>
Это обеспечивает возможность обращения к портам сервиса по имени сервиса.

**Файл описания сервисов (kind: Service)**

Файл описания сервисов `<podName>.yml` генерируется в каталоге `manifests/<namespace>/<podName>/Pod/Service/`.
Все порты docker-сервисов помещаются в один сервис с именем `<podName>` в пространстве имен `<namespace>`.
Это обеспечивает в рамках kubernetes-кластера обращения к портам `Pod`'а по доменным именам:
<pre>
&lt;podName> (в рамках namespace `&lt;namespace>`)
&lt;podName>.&lt;namespace>
&lt;podName>.&lt;namespace>.svc.cluster.local
</pre>

**Файлы описания запросов внешних томов (kind: PersistentVolumeClaim)**

Файлы описания запросов внешних томов  с именами `<podName>-<serviceName>` размещаются в каталоге
`manifests/<namespace>/<podName>/Pod/PersistentVolumeClaim/`.
Каждый том имеет имя `<podName>-<serviceName>`.
Объем выделяемой дисковой памяти: `1Gi`.
При необходимости после генерации YML-файлов этот параметр можно изменить.

**Файлы описания локальных томов (kind: PersistentVolume)**

Для каждого запроса внешнего тома в каталоге `manifests/<namespace>/<podName>/Pod/PersistentVolume/` генерируется файл описания локального тома с именем `<namespace>-<podName>-<serviceName>.yml`.
Каждый описываемый том имеет тот же размер (`1Gi`), что и запрос на внешний том и связывается с ним через описатель:
<pre>
  claimRef:
    name: &lt;podName>-&lt;serviceName>
    namespace: &ltnamespace>
</pre>

Подкаталоги создаваемых томов располагаются в каталоге `<namespace>` каталога, указанным параметром `--pvpath` (по умолчанию `/mnt/PersistentVolumes`). Имя подкаталогов: `<podName>-<serviceName>`.

Если тома создаются для узла `kubernetes`, работающего в `rootless-режиме`, необходимо в параметрах `--user(-u)`, `--group`(-g)` указать имя и группу (при отсутствии флага совпадает с именем пользователя) от имени которого работают контнейнеры узла кластера.

### Тип разворачивания Deployment

**Deploy-файлы типа Deployment (kind: Deployment)**

При типе разворачивания `Deployment` (`--type deployment` или `-t d`) в каталоге `manifests/<namespace>/<podName>/Deployment/` для каждого ` docker-compose сервиса` генерируется YML-файл разворачивания (`kind: Deployment`) `servuceName>.yml`.

Число реплик сервисов (`spec.replicas`) устанавливается в 1-цу.
При необходимости после генерации YML-файлов для `Stateless контейнеров` (не имеющих внешних томом или имеющие тома только на чтение) число реплик можно увеличить до необходимого значения.

**Файлы описания сервисов (kind: Service)**

Файлы описания сервисов `<serviceName>.yml` генерируется в каталоге `manifests/<namespace>/<podName>/Deployment/Service/`.

Следует заметить, что если `docker-compose сервис` принимает обращения по какому-либо порту от других сервисов стека сервисов, до перед запуском `Pod'а` командой `podman-compose` необходимо **обязательно указать этот порт в описателе** `services.<service>.port` `docker-compose файла`.
В противном случае файл описания сервиса `manifests/<namespace>/<podName>/Deployment/Service/<serviceName>.yml` не будет создан и порты контейнера не будет видны под коротким доменным именем `<serviceName>` другими контейнерами данного разворачивания (`Deployment`).

**Файлы описания запросов внешних томов (kind: PersistentVolumeClaim) и файлы описания локальных томов (kind: PersistentVolume)**

Данные файлы генерируются точно таким же образом. как и для разворачивания типа `Pod`.
Более того, файлы, созданные при разворачивании типа `Pod` можно использовать при разворачивании типа `Deployment`.
И наоборот.
Но не стоит использовать эти тома одновременно при обоих разворачиваниях.


## OPTIONS

Флаги команды:

* `--type` (`-t`) - тип разворачивания: `pod` (`p`), `deployment`(`d`). Значение по умолчанию - `pod`.
* `--namespace` (`-n`) - kubernetes namespace. Значение по умолчанию - `default`.
* `--dir` (`-d`) - каталог для генерируемых манифестов. Значение по умолчанию - `manifests`.
* `-pvpath` - каталог монтирования PersistentVolume томов. Значение по умолчанию - `/mnt/PersistentVolumes/`.
* `--user` (`-u`) имя rootless пользователя от которого работает kubernetes . Значение по умолчанию - пустая строка.
* `--group` (`-g`) - группа rootless пользователя от которого работает kubernetes. Значение по умолчанию - `=user`.
* `--debug` - уровень отладки. Значение по умолчанию - `0`.

Позиционные параметры:

1. имя_POD'а- имя развернутого `POD`'а;
2. имя-docker-compose-файла - имя docker-compose файла от которого развернут `POD`


## EXAMPLES

Смотри [podman-compose как средство миграция docker-compose решений в kubernetes: Разворачивание стека сервисов](https://www.altlinux.org/Podman-compose/kubernetes#%D0%A0%D0%B0%D0%B7%D0%B2%D0%BE%D1%80%D0%B0%D1%87%D0%B8%D0%B2%D0%B0%D0%BD%D0%B8%D0%B5_%D1%81%D1%82%D0%B5%D0%BA%D0%B0_%D1%81%D0%B5%D1%80%D0%B2%D0%B8%D1%81%D0%BE%D0%B2)
