# Ingress control plane

`edge/` is the control plane that stands between the policy documents the teams
commit and the proxy in front of the storefront's pods. A controller watches
`config/policies/`, works out which policies are attached to a route, and hands
them to the compiler; whatever the compiler returns is what the proxy is asked
to load for that route.

- `edge/protocol.py` ships in the data-plane release and is shared with the
  proxy, the load reporter and the pod autoscaler, so it stays as it is. It owns
  `Request`, `Step`, `Route` and `Policy`, the lookups `header_value` and
  `read_value`, `apply_rewrite` and `read_rewrite`, `ttl_seconds` and
  `cookie_line`, `normalise_key`, `part`, `fold` and `choose_pod`, the
  precedence rule `rank`, the plan check `check_plan`, and `admit`, which is how
  a committed document is read.
- `edge/compile.py` is ours: `compile_route(route, documents)` returns the pin
  plan a route serves.
- `edge/pin.py` is ours: `pin_parts(request, steps)` returns what one request
  contributes to its pin digest.

## How the edge behaves

A push hands the control plane one route and the policy documents reconciled
onto it. The proxy runs `check_plan` on whatever comes back; a plan it refuses
is not loaded and the route goes on serving the last plan it accepted, which is
why a bad push looks like a change that never took effect rather than an error.

For every request the proxy folds the plan's contributions into a digest and
`choose_pod` turns that into a pod, so two requests that fold to the same parts
land on the same pod. A route serving no plan does not pin at all: its requests
go to the pods in turn.

Policies are attached at two scopes. `scope: fleet` is the platform team's,
attached across several routes; `scope: route` belongs to the team that owns
the route. `rank` is what the plane compares when two of them meet.

## Operations notes

- The controller re-pushes every route it reconciles, several times a day: a
  relabel, a policy edit anywhere in the estate, a controller restart. Nothing
  about the storefront changes on those pushes.
- Header names are case-insensitive at the proxy, so `header_value` finds a
  header whatever way it is spelt in the document.
- Cookie lifetimes are written both ways in the estate and both spellings are
  committed today; `ttl_seconds` is what the plane reads them with, and
  `cookie_line` renders what the proxy sets.

## Drills

`project_records/` holds the four drills the platform replays before a policy
push goes out. Each one looks at a different part of the edge, so the replay
prints different columns for each.

- `run_project(action="status")` lists the edge files, the routes and their
  pods, the committed policy documents and the drills.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  drill against the current workspace on a throwaway copy and prints what the
  plane and the proxy did at every step of it.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can push any policy set of your own
  through `compile_route` and fold any request you like.
