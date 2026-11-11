"""Local, model-driven Reverse Turing rehearsal. NOT part of the 24-trial study.

One localhost relay; role-scoped HTTP clients; real OpenAI-compatible models
when provider=compatible, or explicit synthetic ScriptedDemo plumbing checks.
The operator coordinates the roles within one Python process. This does NOT
establish independent model-backend isolation or prevent an operator with
server access from observing truth. No human actors are simulated.

Artifacts are locally private; raw controller exports can contain confidential
participant text and should never be committed to a public repository.
"""
from __future__ import annotations

import argparse
import hashlib
from http.server import ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
from threading import Event, Thread
import time

from experiments.check_conductor_delivery import assess_delivery
from game.agents import (
    Agent, AdapterError, CompatibleChat, RelayClient, ScriptedDemo,
    endpoint_url,
)
from game.conductor_receipt import ConductorReceipt
from game.engine import Game, RuleError
from game.server import handler_factory, run_release_worker


ROLES = ("conductor", "machine_A", "machine_B", "replacement_A", "replacement_B")
CONDITIONS = ("unchanged", "machineA", "machineB")
MAX_WALL_SECONDS = 1800


class RehearsalError(RuntimeError):
    pass


def _new_json(path: Path, data):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def _hash(value):
    blob = json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def validate_config(raw, required_roles):
    if not isinstance(raw, dict) or set(raw) != {"roles"}:
        raise RehearsalError("Model config needs exactly one 'roles' object")
    roles = raw["roles"]
    if not isinstance(roles, dict) or set(roles) != set(required_roles):
        raise RehearsalError("Model config must name only the active rehearsal roles")
    normalized = {}
    for role in required_roles:
        spec = roles[role]
        if not isinstance(spec, dict) or not (
            {"endpoint", "model"} <= set(spec) <=
            {"endpoint", "model", "api_key_env", "max_output_tokens"}
        ):
            raise RehearsalError("Role model config contains missing or unsafe fields")
        model = spec["model"]
        if not isinstance(model, str) or not model.strip():
            raise RehearsalError("Each model must have a nonempty identifier")
        try:
            endpoint = endpoint_url(spec["endpoint"], relay=False)
        except AdapterError as exc:
            raise RehearsalError(str(exc)) from None
        name = spec.get("api_key_env")
        if name is not None and (
            not isinstance(name, str)
            or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None
            or name.startswith("RTT_ROLE_")
        ):
            raise RehearsalError("api_key_env must name a safe environment variable")
        tokens = spec.get("max_output_tokens", 256)
        if type(tokens) is not int or not 16 <= tokens <= 2048:
            raise RehearsalError("max_output_tokens must be an integer from 16 to 2048")
        normalized[role] = {
            "endpoint": endpoint, "model": model.strip(),
            "api_key_env": name, "max_output_tokens": tokens,
        }
    return normalized


class MeasuredModel:
    """Record actual provider call counts, durations, and hashes, never keys."""

    def __init__(self, role, backend, ledger):
        self.role = role
        self.backend = backend
        self.ledger = ledger

    def complete(self, messages):
        started = time.monotonic_ns()
        entry = {
            "role": self.role,
            "input_sha256": _hash(messages),
            "input_chars": sum(len(str(m.get("content", ""))) for m in messages),
            "start_monotonic_ns": started,
        }
        try:
            response = self.backend.complete(messages)
            entry.update({
                "success": True,
                "output_sha256": hashlib.sha256(response.encode("utf-8")).hexdigest(),
                "output_chars": len(response),
            })
            return response
        except Exception as exc:
            entry.update({
                "success": False,
                "error_type": type(exc).__name__,
            })
            raise
        finally:
            ended = time.monotonic_ns()
            entry["elapsed_ms"] = round((ended - started) / 1e6, 3)
            entry["end_monotonic_ns"] = ended
            self.ledger.append(entry)


def _require_parameters(mode, condition, link_after, gate_seconds,
                        poll_seconds, max_wall_seconds):
    if mode not in ("smoke", "unbound-pilot"):
        raise RehearsalError("Choose smoke or unbound-pilot")
    if condition not in CONDITIONS:
        raise RehearsalError("Rehearsal cannot create a fake human participant")
    if link_after not in ("on", "off"):
        raise RehearsalError("Link factor must be on or off")
    if type(gate_seconds) not in (int, float) or not math.isfinite(gate_seconds):
        raise RehearsalError("Gate must be finite")
    if mode == "smoke" and not 1 <= gate_seconds <= 600:
        raise RehearsalError("Open smoke gate must be 1–600 seconds")
    if mode == "unbound-pilot" and gate_seconds != 45:
        raise RehearsalError("Unbound pilot uses the real 45-second fixed gate")
    if type(poll_seconds) not in (int, float) or not .1 <= poll_seconds <= 3:
        raise RehearsalError("Poll interval must be 0.1–3 seconds")
    if (type(max_wall_seconds) not in (int, float)
            or not 1 <= max_wall_seconds <= MAX_WALL_SECONDS):
        raise RehearsalError("Bound maximum wall time to 1–1800 seconds")


def run_rehearsal(*, outdir, provider, model_map=None, mode="unbound-pilot",
                  condition="machineA", link_after="off", gate_seconds=45.,
                  poll_seconds=.1, max_wall_seconds=900.,
                  private_handoff=True):
    """Execute one non-study machine-only game and preserve success or failure.

    Returns a manifest. Raises only for invalid preflight config or invalid
    output directory. In-experiment errors are preserved and labeled FAILED.
    """
    _require_parameters(mode, condition, link_after, gate_seconds,
                        poll_seconds, max_wall_seconds)
    if provider not in ("compatible", "scripted"):
        raise RehearsalError("Provider must be compatible or scripted")
    if type(private_handoff) is not bool:
        raise RehearsalError("private_handoff must be boolean")
    replacement = {"machineA": "replacement_A", "machineB": "replacement_B"}.get(condition)
    roles = ("conductor", "machine_A", "machine_B") + ((replacement,) if replacement else ())
    if provider == "compatible":
        specs = validate_config(model_map, roles)
    elif model_map is not None:
        raise RehearsalError("Scripted tests cannot accept model endpoint configuration")
    else:
        specs = {role: {"provider": "scripted"} for role in roles}

    destination = Path(outdir).expanduser()
    if destination.name.startswith("RTT-"):
        raise RehearsalError("Do not use a preregistered RTT-XX trial ID for a rehearsal")
    if len(destination.name) > 60 or not re.fullmatch(r"[a-zA-Z0-9_.-]+", destination.name):
        raise RehearsalError("Use a short safe rehearsal directory name")
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    manifest = {
        "schema": "reverse-turing-rehearsal/v1",
        "evidence_status": "non_study_rehearsal",
        "is_preregistered_trial": False,
        "provider": provider,
        "mode": mode, "condition": condition, "link_after": link_after,
        "gate_seconds": 45.0 if mode == "unbound-pilot" else float(gate_seconds),
        "poll_seconds": poll_seconds, "max_wall_seconds": max_wall_seconds,
        "private_handoff": private_handoff,
        "model_configuration_sha256": _hash(specs),
        "model_configuration_public": specs,
        "external_model_backend_isolation_attested": False,
        "human_participants": 0,
        "status": "started",
        "errors": [],
    }
    game = None
    server = None
    server_thread = None
    worker = None
    stop = Event()
    receipt = None
    calls = []
    deadline = time.monotonic() + max_wall_seconds
    terminal_status = "incomplete"
    try:
        game = Game()
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), handler_factory(game)
        )
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        worker = Thread(
            target=run_release_worker,
            args=(game, stop, .05),
            daemon=True,
        )
        worker.start()

        origin = f"http://127.0.0.1:{server.server_port}"
        controller = RelayClient(origin, game.tokens["controller"])
        if mode == "unbound-pilot":
            controller.act("configure_pilot")
        else:
            controller.act("configure_pacing", seconds=gate_seconds)
            controller.act("configure", links={"A_to_B": True, "B_to_A": True})
        actors = {}
        for role in roles:
            if provider == "scripted":
                backend = ScriptedDemo()
            else:
                spec = specs[role]
                varname = spec["api_key_env"]
                if varname is not None and not os.environ.get(varname):
                    raise RehearsalError(
                        "Missing model credential environment variable for " + role
                    )
                backend = CompatibleChat(
                    spec["endpoint"], spec["model"],
                    api_key=os.environ.get(varname, "") if varname else "",
                    max_tokens=spec["max_output_tokens"],
                )
            role_relay = RelayClient(origin, game.tokens[role])
            if role == "conductor":
                receipt = ConductorReceipt(
                    role_relay, destination / "conductor.jsonl",
                    "REHEARSAL-" + destination.name,
                    poll_seconds=poll_seconds,
                )
                role_relay = receipt
            actors[role] = Agent(
                role, role_relay, MeasuredModel(role, backend, calls),
                question_budget=8 if mode == "unbound-pilot" else 4,
                private_handoff=private_handoff and role != "conductor",
            )

        completed = False
        while time.monotonic() < deadline:
            ctrl = controller.view()
            if ctrl["timing_violations"]:
                raise RehearsalError("Server reports pacing violations")
            if ctrl["baseline_ready"] and not ctrl["intervened"]:
                if mode == "unbound-pilot" and ctrl["pilot_phase"] != "transition":
                    raise RehearsalError("Baseline transition barrier missing")
                on = link_after == "on"
                controller.act(
                    "intervene", condition=condition,
                    links={"A_to_B": on, "B_to_A": on}, human_gateway=False,
                )
                if mode == "unbound-pilot":
                    controller.act("resume_pilot")

            c_status = actors["conductor"].step()
            if c_status == "verdict":
                completed = True
                break
            active = controller.view()["active"]
            for role in set(active.values()):
                if role not in actors:
                    raise RehearsalError("Unexpected or unauthorized actor in model-only rehearsal")
                actors[role].step()
            time.sleep(poll_seconds)
        if not completed:
            raise RehearsalError("Rehearsal exceeded its fixed wall-clock budget")

        controller.act("reveal")
        if mode == "unbound-pilot" and not controller.view()["pilot_valid_for_primary"]:
            raise RehearsalError("Unbound protocol did not complete its eight questions")
        terminal_status = "verdict"
        manifest["status"] = "completed"
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["errors"].append({
            "kind": type(exc).__name__,
            "detail": str(exc)[:500],
        })
        if game is not None and mode == "unbound-pilot":
            try:
                if not game.pilot_aborted and not game.revealed:
                    game.act("controller", "abort_pilot", {
                        "reason": "Rehearsal error; retain incomplete export"
                    })
            except (RuleError, ValueError):
                pass
    finally:
        if receipt is not None:
            receipt.close(status=terminal_status)
        stop.set()
        if worker is not None:
            worker.join(timeout=2)
        if server is not None:
            server.shutdown()
            server.server_close()
        if server_thread is not None:
            server_thread.join(timeout=2)
        if game is not None:
            exported = game.export()
            _new_json(destination / "controller.json", exported)
            if receipt is not None:
                try:
                    record = [
                        json.loads(line) for line in
                        (destination / "conductor.jsonl").read_text(
                            encoding="utf-8").splitlines()
                        if line.strip()
                    ]
                    manifest["delivery"] = assess_delivery(
                        exported, record,
                        require_complete_pilot=mode == "unbound-pilot",
                    )
                except (OSError, ValueError) as exc:
                    manifest["delivery"] = {
                        "within_one_second_given_same_clock": False,
                        "errors": ["receipt_analysis_failed", type(exc).__name__],
                    }
            else:
                manifest["delivery"] = {
                    "within_one_second_given_same_clock": False,
                    "errors": ["conductor_receipt_not_started"],
                }
        _new_json(destination / "model_calls.json", calls)
        manifest["model_call_count"] = len(calls)
        manifest["actual_private_message_count"] = (
            len(game.private) if game is not None else None
        )
        manifest["confirmatory_ready"] = False
        _new_json(destination / "manifest.json", manifest)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="One non-study machine-only Reverse Turing rehearsal"
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--provider", required=True, choices=("scripted", "compatible"))
    parser.add_argument("--models-config",
                        help="private JSON of per-role compatible model endpoints")
    parser.add_argument("--mode", choices=("smoke", "unbound-pilot"),
                        default="unbound-pilot")
    parser.add_argument("--condition", choices=CONDITIONS, default="machineA")
    parser.add_argument("--link-after", choices=("on", "off"), default="off")
    parser.add_argument("--gate-seconds", type=float, default=45.)
    parser.add_argument("--poll-seconds", type=float, default=.1)
    parser.add_argument("--max-wall-seconds", type=float, default=900.)
    parser.add_argument("--no-private-handoff", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = None
        if args.models_config is not None:
            config = json.loads(Path(args.models_config).read_text(encoding="utf-8"))
        report = run_rehearsal(
            outdir=args.output_dir, provider=args.provider, model_map=config,
            mode=args.mode, condition=args.condition, link_after=args.link_after,
            gate_seconds=args.gate_seconds, poll_seconds=args.poll_seconds,
            max_wall_seconds=args.max_wall_seconds,
            private_handoff=not args.no_private_handoff,
        )
        print("Rehearsal:", report["status"], "model calls:",
              report["model_call_count"], "private messages:",
              report["actual_private_message_count"])
        print("Server->C timing (conditional):",
              report.get("delivery", {}).get("within_one_second_given_same_clock"))
        print("Study observations collected: 0")
        return 0 if report["status"] == "completed" else 2
    except (RehearsalError, ValueError, OSError, TypeError) as exc:
        print("Rehearsal setup rejected:", str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
