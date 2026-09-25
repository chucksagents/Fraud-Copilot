# infra/openshift/

Deploys `services/alert-api` to a Red Hat Developer Sandbox OpenShift
project, replacing the `cloudflared` tunnel with a stable, public HTTPS
route -- the tunnel's "grabs a new random URL every restart, re-import the
Orchestrate tool every time" problem (see `orchestrate/README.md`) goes
away once Orchestrate points at this instead.

Only `alert-api` is deployed here. `customer-context-api` and `action-api`
are still stub READMEs (Day 3/4 handoff item #4, still undecided) -- nothing
to deploy for those yet. Kafka itself stays on Confluent Cloud; this only
puts the FastAPI service on a cluster.

## Prerequisites

1. **Reserve a Developer Sandbox trial** at
   [developers.redhat.com/developer-sandbox](https://developers.redhat.com/developer-sandbox)
   if you haven't already (free, 30-day trial, renewable). Log in with your
   Red Hat account and follow its setup flow.
2. **Install the `oc` CLI** if you don't have it: `brew install openshift-cli`,
   or download it from the sandbox web console's "?" menu -> "Command line
   tools".
3. **Get a login command**: in the sandbox web console, click your name
   (top right) -> "Copy login command" -> "Display Token", then run the
   `oc login --token=... --server=...` command it gives you.
4. **Switch to your `-dev` project**: the sandbox provisions a few
   namespaces per user (typically `<username>-dev`, `-stage`, `-tools`).
   Use the `-dev` one: `oc project <username>-dev` (`oc projects` lists what
   you have).

## Setup, in order

### 1. Create the Kafka credentials secret

Reuses `infra/.env` as-is -- same Confluent Cloud credentials the local
alert-api, producers, and Flink already use:

```bash
oc create secret generic alert-api-env --from-env-file=infra/.env
```

(Harmless if this also pulls in unrelated keys like `WXO_*` -- they're just
ignored env vars in the container.)

### 2. Apply the manifests

From the repo root:

```bash
oc apply -f infra/openshift/imagestream.yaml
oc apply -f infra/openshift/buildconfig.yaml
oc apply -f infra/openshift/pvc.yaml
oc apply -f infra/openshift/deployment.yaml
oc apply -f infra/openshift/service.yaml
oc apply -f infra/openshift/route.yaml
```

The Deployment's pod will fail to pull its image until step 4 below --
that's expected, it'll recover once the build finishes.

### 3. Image resolution -- already handled, no action needed

`deployment.yaml` carries an `image.openshift.io/triggers` annotation that
watches the `alert-api:latest` ImageStreamTag and patches the pod's `image:`
field with the real internal registry pullspec whenever a build lands --
this is what actually resolves `image: alert-api:latest` into something
pullable, and it also means every future `oc start-build` auto-triggers a
new rollout with no extra `oc rollout restart` needed.

(An earlier version of this README had you run `oc set image-lookup
alert-api` for this instead. That's the more commonly-documented mechanism,
but on this Developer Sandbox cluster it didn't actually rewrite the
Deployment's pod spec -- pods kept trying to pull the literal string
`alert-api:latest` straight from Docker Hub and failing. The trigger
annotation is a different, more reliable mechanism and is what's now baked
into the manifest. `oc set image-lookup alert-api` is harmless to run too if
you want the ImageStream itself locally-resolvable for other purposes, but
it's not what makes this Deployment work.)

### 4. Build the image

Binary build straight from your local `services/alert-api/` directory --
no git push, no external registry:

```bash
oc start-build alert-api --from-dir=services/alert-api --follow
```

If this errors with something like `docker strategy is forbidden` (some
managed OpenShift projects restrict the Docker build strategy for
non-admin users, unlike self-managed clusters), fall back to an S2I build
off a Python builder image instead:

```bash
oc new-build python:3.12-ubi9 --binary --name=alert-api
oc start-build alert-api --from-dir=services/alert-api --follow
```

(S2I's Python builder auto-installs `requirements.txt` and needs the app
importable as `app.main:app` from the directory root, which it already is
-- no Dockerfile involved in this fallback path, so it also sidesteps the
Dockerfile's `chgrp`/`chmod` line entirely and relies on the builder
image's own arbitrary-UID support instead.)

### 5. Watch it roll out

```bash
oc rollout status deployment/alert-api
oc get pods -l app=alert-api -w
```

**If you re-apply `deployment.yaml` or re-trigger a rollout while an old
pod is stuck (`ImagePullBackOff`, `CrashLoopBackOff`, etc.) instead of
cleanly terminating**, the new pod can sit in `ContainerCreating`
indefinitely with a `FailedAttachVolume` / `Multi-Attach error` event
(`oc describe pod <new-pod>` to confirm). The PVC is `ReadWriteOnce`, so
only one pod can hold it at a time, and Kubernetes won't force-detach it
from a stuck-but-technically-still-running old pod. Fix: delete the old
**ReplicaSet** outright (not just its pod -- deleting only the pod lets the
ReplicaSet controller immediately recreate another one and re-take the
volume):

```bash
oc get rs -l app=alert-api
oc delete rs <old-replicaset-name>
```

the new pod should then finish attaching within a few seconds.

### 6. Get the route and verify

```bash
oc get route alert-api -o jsonpath='{.spec.host}{"\n"}'
curl https://<the host above>/health
curl https://<the host above>/alerts | python3 -m json.tool
```

You should see the same alerts your local `GET /alerts` returns -- this
deployment consumes `fraud-alerts` independently (its own consumer group,
see `deployment.yaml`'s comments), starting from `auto.offset.reset=earliest`,
so it backfills everything already on the topic.

### 7. Point Orchestrate at it

In `orchestrate/tools/alert_api_tools.py`, replace `ALERT_API_BASE_URL`
with `https://<route host>`, then:

```bash
orchestrate tools import -k python -f orchestrate/tools/alert_api_tools.py \
  -r orchestrate/tools/requirements.txt
```

This works whether Orchestrate is running as Developer Edition (local
Docker) or SaaS -- unlike `host.docker.internal` or a tunnel, a Route is a
real public HTTPS endpoint either way. You can stop running `cloudflared`
at this point.

## Redeploying after a code change

```bash
oc start-build alert-api --from-dir=services/alert-api --follow
oc rollout status deployment/alert-api
```

`oc rollout restart` shouldn't be necessary anymore -- the
`image.openshift.io/triggers` annotation on `deployment.yaml` (see step 3
above) rolls out a new pod automatically as soon as the build lands a new
image on the `alert-api:latest` tag. If a rollout ever seems to hang after
a build, check for the stuck-old-pod/PVC-Multi-Attach situation described
in step 5 first before assuming the trigger didn't fire.

## Known limitations (demo-scope, same spirit as `services/alert-api/README.md`'s corners)

- **Single replica.** SQLite doesn't handle concurrent writers safely --
  don't scale this past `replicas: 1` without moving off SQLite first.
- **Pods recycle every 12h.** Developer Sandbox kills pods after 12
  consecutive hours of uptime regardless of load. Harmless here since the
  Deployment just recreates it and the SQLite file survives on the PVC --
  but don't be surprised by a restart mid-demo if it's been running a
  while.
- **Sandbox itself expires after 30 days** (renewable). This deployment
  isn't meant to be a permanent home for the service.
- **`alert-api-env` secret is only as safe as the sandbox project's RBAC.**
  Fine for a personal trial namespace; wouldn't reuse this pattern
  (plaintext-from-.env into a bare Secret) for anything with real
  customer data behind it.
- **No autoscaling, no PodDisruptionBudget, no NetworkPolicy** -- none of
  that's needed for a single-replica personal demo, but worth knowing it's
  absent if this ever needs to look more production-like.

## Files

```
imagestream.yaml   tracks the built image
buildconfig.yaml   binary Docker build from services/alert-api/Dockerfile
pvc.yaml           500Mi, for alerts.db persistence across restarts
deployment.yaml    1 replica, image trigger for auto-rollout, /health probes
service.yaml       ClusterIP :8000
route.yaml         edge-TLS public route -- this is the new ALERT_API_BASE_URL
```

Note: `deployment.yaml` deliberately does **not** set `securityContext.fsGroup`
(an earlier version pinned `fsGroup: 0` for PVC writability, which works on
a self-managed cluster but Developer Sandbox's `restricted-v2`/`restricted-v3`
SCCs reject any hardcoded fsGroup, including 0, with `0 is not an allowed
group`). Leaving it unset lets Sandbox auto-assign one from its own
namespace-specific range instead, which still makes the PVC writable via a
supplemental group regardless of the container's primary group.

(No `secret.yaml` on purpose -- created directly from `infra/.env` via the
CLI in step 1 above, same gitignore-don't-commit-credentials convention as
`infra/.env` itself.)
