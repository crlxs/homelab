"""Offline behavior tests: real curl/jq bootstrap against local fake APIs."""

import copy
import base64
import json
from pathlib import Path
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from ansible.plugins.filter.core import FilterModule
from jinja2 import Environment, StrictUndefined
from jinja2.filters import do_default
import yaml


ROOT = Path(__file__).resolve().parents[1]
ENV = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
ENV.filters.update(FilterModule().filters())
# Ansible's default filter expects Ansible's undefined marker. This standalone
# Jinja environment uses StrictUndefined, so use its matching default filter.
ENV.filters["default"] = do_default


class FakeAPI(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def dispatch(self, method):
        state = self.server.state
        path = urlsplit(self.path).path
        data = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if path == "/ping":
            return self.reply({"status": "OK"})
        if path == "/api":
            query = parse_qs(urlsplit(self.path).query)
            query.update(parse_qs(data.decode()))
            query = {k: v[0] for k, v in query.items()}
            if query.get("mode") == "version":
                return self.reply({"version": "5.1.3"})
            if query.get("apikey") != "sab-key":
                return self.reply({"error": "API key incorrect"}, 403)
            section, keyword = query["section"], query.get("keyword")
            config = state["config"]
            if query["mode"] == "get_config":
                if section == "misc":
                    result = {keyword: config[section].get(keyword, "")}
                else:
                    result = [copy.deepcopy(config[section][keyword])] if keyword in config[section] else []
                if isinstance(result, list):
                    for entry in result:
                        if "password" in entry:
                            entry["password"] = "********"
                elif keyword == "password":
                    result[keyword] = "********" if result[keyword] else ""
                return self.reply({"config": {section: result}})
            if state.get("reject_writes"):
                return self.reply({"status": False, "error": "Config is locked"})
            state["writes"].append(copy.deepcopy(query))
            if section == "misc":
                config[section][keyword] = query["value"]
                result = {keyword: query["value"]}
            else:
                name = query["name"]
                config[section].setdefault(name, {}).update(
                    {k: v for k, v in query.items() if k not in ["mode", "section", "apikey", "output"]}
                )
                result = [config[section][name]]
            return self.reply({"config": {section: result}})
        if self.headers.get("X-Api-Key") != state["key"]:
            return self.reply({"error": "Incorrect Arr key"}, 403)
        resource = path.split("/")[3]
        if resource == "indexer" and path.endswith("/schema"):
            return self.reply([{"name": "NZBgeek", "implementation": "Newznab",
                                "configContract": "NewznabSettings", "fields": [
                                    {"name": "apiPath", "value": "/api", "type": "textbox"}]}])
        if resource == "appprofile":
            return self.reply([{"id": 1, "enableRss": True, "enableAutomaticSearch": True,
                                "enableInteractiveSearch": True}])
        if resource == "command":
            state["writes"].append((method, path))
            return self.reply({"id": 1})
        if path.endswith("/test"):
            payload = json.loads(data)
            saved = next(c for c in state[resource] if c["id"] == payload["id"])
            key = next(f.get("value") for f in saved["fields"] if f["name"] == "apiKey")
            expected = "sab-key" if resource == "downloadclient" else saved["name"].lower() + "-key"
            return self.reply({} if key == expected else {"error": "Stale credential"}, 200 if key == expected else 400)
        if resource == "config":
            if method == "GET":
                return self.reply(state["auth"])
            state["auth"].update(json.loads(data))
            state["writes"].append((method, path))
            return self.reply(state["auth"])
        collection = state[resource]
        if method == "GET":
            if state.get("mask_secrets"):
                response = copy.deepcopy(collection)
                for provider in response:
                    for field in provider.get("fields", []):
                        if field["name"] == "apiKey":
                            field["value"] = "********"
                return self.reply(response)
            return self.reply(collection)
        payload = json.loads(data)
        for field in payload.get("fields", []):
            field.setdefault("type", "textbox")
            field.setdefault("advanced", False)
        state["writes"].append((method, path))
        if method == "POST":
            payload["id"] = len(collection) + 1
            collection.append(payload)
        else:
            for entry in collection:
                if entry["id"] == payload["id"]:
                    entry.update(payload)
                    break
        return self.reply(payload)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.servers = {}
        for app in ["radarr", "sonarr", "prowlarr", "sabnzbd"]:
            server = ThreadingHTTPServer(("127.0.0.1", 0), FakeAPI)
            server.state = {
                "key": f"{app}-key", "writes": [], "auth": {"id": 1, "username": ""},
                "rootfolder": [], "downloadclient": [], "applications": [], "indexer": [],
                "config": {"misc": {}, "categories": {}, "servers": {}},
            }
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.servers[app] = server
        self.ports = {name: server.server_port for name, server in self.servers.items()}
        self.context = {
            "servarr_endpoints": {name: "127.0.0.1" for name in self.servers},
            "servarr_ports": self.ports,
            "sabnzbd_web_port": self.ports["sabnzbd"], "servarr_ui_username": "admin",
            "radarr_root_folder": "/opt/media/movies", "sonarr_root_folder": "/opt/media/tv",
            "nzbgeek_indexer_name": "NZBGeek", "nzbgeek_base_url": "https://api.nzbgeek.info",
        }
        self.script = ENV.from_string(
            (ROOT / "roles/servarr/templates/bootstrap-servarr.sh.j2").read_text()
        ).render(self.context)
        self.payload = {
            "servarr_ui_password": "shared ' & $() password",
            "radarr_api_key": "radarr-key", "sonarr_api_key": "sonarr-key",
            "prowlarr_api_key": "prowlarr-key", "sabnzbd_api_key": "sab-key",
            "sabnzbd_ui_username": "admin", "sabnzbd_ui_password": "shared ' & $() password",
            "sabnzbd_incomplete_dir": "/opt/media/downloads/incomplete",
            "sabnzbd_complete_dir": "/opt/media/downloads/complete",
            "sabnzbd_radarr_category": "radarr", "sabnzbd_sonarr_category": "sonarr",
            "sabnzbd_prowlarr_category": "prowlarr", "sabnzbd_provider_name": "primary",
            "sabnzbd_provider_host": "news.example.test", "sabnzbd_provider_port": "563",
            "sabnzbd_provider_username": "provider-user", "sabnzbd_provider_password": "secret & ' + %",
            "sabnzbd_provider_connections": "10", "sabnzbd_provider_ssl": True,
            "sabnzbd_provider_ssl_verify": 3, "sabnzbd_provider_priority": 0,
            "nzbgeek_api_key": "fixture-geek-key",
        }

    def tearDown(self):
        for server in self.servers.values():
            server.shutdown()
            server.server_close()

    def run_bootstrap(self, success=True):
        result = subprocess.run(
            ["sh", "-c", self.script], input=json.dumps(self.payload),
            text=True, capture_output=True, timeout=30,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(self.payload["servarr_ui_password"], result.stdout + result.stderr)
        self.assertNotIn(self.payload["sabnzbd_provider_password"], result.stdout + result.stderr)
        return result

    def test_first_run_then_unchanged_rerun(self):
        syntax = subprocess.run(["sh", "-n"], input=self.script, text=True, capture_output=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        self.assertEqual(self.run_bootstrap().stdout.strip(), "CHANGED")
        for name in ["radarr", "sonarr", "prowlarr"]:
            state = self.servers[name].state
            self.assertEqual(state["auth"]["password"], self.payload["servarr_ui_password"])
            client = state["downloadclient"][0]
            fields = {f["name"]: f["value"] for f in client["fields"]}
            self.assertEqual(fields["host"], "127.0.0.1")
            self.assertEqual(fields["port"], self.ports["sabnzbd"])
            self.assertEqual(fields["apiKey"], "sab-key")
        self.assertEqual(self.servers["radarr"].state["rootfolder"][0]["path"], "/opt/media/movies")
        self.assertEqual(self.servers["sonarr"].state["rootfolder"][0]["path"], "/opt/media/tv")
        config = self.servers["sabnzbd"].state["config"]
        self.assertEqual(config["misc"]["password"], self.payload["servarr_ui_password"])
        self.assertEqual(config["misc"]["download_dir"], "/opt/media/downloads/incomplete")
        self.assertEqual(config["servers"]["primary"]["ssl"], "1")
        self.assertEqual(config["servers"]["primary"]["ssl_verify"], "3")
        self.assertEqual(set(config["categories"]), {"radarr", "sonarr", "prowlarr"})
        indexer = self.servers["prowlarr"].state["indexer"][0]
        self.assertEqual(indexer["appProfileId"], 1)
        self.assertEqual({f["name"]: f["value"] for f in indexer["fields"]}["apiKey"], "fixture-geek-key")
        writes = sum(len(s.state["writes"]) for s in self.servers.values())
        self.assertEqual(self.run_bootstrap().stdout.strip(), "OK")
        self.assertEqual(writes, sum(len(s.state["writes"]) for s in self.servers.values()))

    def test_indexer_key_rotation_preserves_custom_fields(self):
        self.run_bootstrap()
        indexer = self.servers["prowlarr"].state["indexer"][0]
        indexer["priority"] = 7
        self.payload["nzbgeek_api_key"] = "rotated-fixture-key"
        self.assertEqual(self.run_bootstrap().stdout.strip(), "CHANGED")
        self.assertEqual(len(self.servers["prowlarr"].state["indexer"]), 1)
        self.assertEqual(indexer["priority"], 7)
        self.assertEqual(self.run_bootstrap().stdout.strip(), "OK")

    def test_preserve_differently_named_nzbgeek_indexer(self):
        custom = {"name": "My Geek", "implementation": "Newznab", "fields": [
            {"name": "baseUrl", "value": "https://api.nzbgeek.info"}], "id": 9}
        self.servers["prowlarr"].state["indexer"].append(custom.copy())
        self.run_bootstrap()
        self.assertEqual(self.servers["prowlarr"].state["indexer"], [custom])

    def test_missing_empty_api_fields_are_unchanged(self):
        self.run_bootstrap()
        for app in ["radarr", "sonarr", "prowlarr"]:
            for field in self.servers[app].state["downloadclient"][0]["fields"]:
                if field["name"] == "urlBase":
                    field.pop("value")
        self.assertEqual(self.run_bootstrap().stdout.strip(), "OK")

    def test_masked_working_credentials_are_unchanged_but_stale_keys_repaired(self):
        self.run_bootstrap()
        for app in ["radarr", "sonarr", "prowlarr"]:
            self.servers[app].state["mask_secrets"] = True
        # Leave the indexer API key visible, as it is on the live Prowlarr API.
        self.servers["prowlarr"].state["indexer"] = []
        self.servers["prowlarr"].state["indexer"].append({"id": 9, "name": "My Geek", "implementation": "Newznab",
            "fields": [{"name": "baseUrl", "value": "https://api.nzbgeek.info"}]})
        self.assertEqual(self.run_bootstrap().stdout.strip(), "OK")
        for app in ["radarr", "sonarr", "prowlarr"]:
            for field in self.servers[app].state["downloadclient"][0]["fields"]:
                if field["name"] == "apiKey":
                    field["value"] = "stale-key"
        for field in self.servers["prowlarr"].state["applications"][0]["fields"]:
            if field["name"] == "apiKey":
                field["value"] = "stale-key"
        self.assertEqual(self.run_bootstrap().stdout.strip(), "CHANGED")
        self.assertEqual(self.run_bootstrap().stdout.strip(), "OK")

    def test_repair_endpoints_without_resetting_user_configuration(self):
        self.run_bootstrap()
        state = self.servers["radarr"].state
        client = state["downloadclient"][0]
        client["fields"].append({"name": "customSetting", "value": "keep-me"})
        for field in client["fields"]:
            if field["name"] == "host":
                field["value"] = "sabnzbd"
            elif field["name"] == "apiKey":
                field["value"] = "stale-key"
        state["auth"]["password"] = "user-changed-password"
        provider = self.servers["sabnzbd"].state["config"]["servers"]["primary"]
        provider["password"] = "user-changed-provider-password"
        provider["ssl"] = "0"
        application = self.servers["prowlarr"].state["applications"][0]
        application["syncLevel"] = "addOnly"
        for field in application["fields"]:
            if field["name"] == "baseUrl":
                field["value"] = "http://radarr:7878"
        self.assertEqual(self.run_bootstrap().stdout.strip(), "CHANGED")
        self.assertEqual(state["auth"]["password"], "user-changed-password")
        self.assertEqual(provider["password"], "user-changed-provider-password")
        self.assertEqual(provider["ssl"], "1")
        fields = {f["name"]: f["value"] for f in client["fields"]}
        self.assertEqual(fields["host"], "127.0.0.1")
        self.assertEqual(fields["apiKey"], "sab-key")
        self.assertEqual(fields["customSetting"], "keep-me")
        self.assertEqual(application["syncLevel"], "addOnly")
        self.assertEqual(self.run_bootstrap().stdout.strip(), "OK")

    def test_preserve_differently_named_user_managed_client(self):
        custom = {"name": "My Usenet", "implementation": "Sabnzbd", "fields": [], "id": 9}
        self.servers["sonarr"].state["downloadclient"].append(custom.copy())
        self.run_bootstrap()
        self.assertEqual(self.servers["sonarr"].state["downloadclient"], [custom])

    def test_sab_semantic_api_failure_stops_bootstrap(self):
        self.servers["sabnzbd"].state["reject_writes"] = True
        result = self.run_bootstrap(success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("CHANGED", result.stdout)


class SABAPIKeyParsingTests(unittest.TestCase):
    def test_configobj_formatting_and_other_sections(self):
        tasks = yaml.safe_load(
            (ROOT / "roles/servarr/tasks/sabnzbd-api-key.yaml").read_text()
        )
        expression = tasks[0]["ansible.builtin.set_fact"]["sabnzbd_api_key"]
        cases = [
            ("[misc]\napi_key = fixture-key\n", "fixture-key"),
            ("[misc]\n    api_key = fixture-key\n", "fixture-key"),
            ('[misc]\r\n\tapi_key = "fixture-key"\r\n', "fixture-key"),
            ("[misc]\n  api_key = 'fixture-key' # comment\n", "fixture-key"),
            ("__version__ = 19\n[misc]\n  api_key = fixture-key\n"
             "[indexers]\n[[example]]\napi_key = different-key\n", "fixture-key"),
            ("[indexers]\napi_key = wrong-key\n[misc]\n  api_key = fixture-key\n", "fixture-key"),
            ("[misc]\napi_key = \"\"\n", ""),
            ("[misc]\nhost = 0.0.0.0\n[other]\napi_key = wrong-key\n", ""),
            ("[other]\napi_key = wrong-key\n", ""),
        ]
        for content, expected in cases:
            with self.subTest(content=content):
                actual = ENV.from_string(expression).render(
                    sabnzbd_config={"content": base64.b64encode(content.encode()).decode()},
                    **tasks[0]["vars"],
                )
                self.assertEqual(actual, expected)


class IdentityMappingTests(unittest.TestCase):
    def test_gpu_option_order_does_not_trigger_a_restart(self):
        tasks = yaml.safe_load((ROOT / "roles/proxmox_lxc/tasks/gpu-devices.yaml").read_text())
        source = tasks[1]["ansible.builtin.set_fact"]["servarr_ct_gpu_changed"]
        for device in ["/dev/nvidia0,uid=1500,gid=1500,mode=0660",
                       "path=/dev/nvidia0,gid=1500,mode=660,uid=1500"]:
            result = ENV.from_string(source).render(
                servarr_ct_gpu_changed=False, existing_device=device,
                servarr_uid=1500, servarr_gid=1500, item="/dev/nvidia0",
            )
            self.assertEqual(result.strip(), "False")
        result = ENV.from_string(source).render(
            servarr_ct_gpu_changed=False, existing_device="/dev/nvidia0,uid=0,gid=0,mode=0660",
            servarr_uid=1500, servarr_gid=1500, item="/dev/nvidia0",
        )
        self.assertEqual(result.strip(), "True")

    def test_snapshot_guard_regex_is_valid(self):
        tasks = yaml.safe_load((ROOT / "roles/proxmox_lxc/tasks/container.yaml").read_text())
        task = next(t for t in tasks if "snapshot identity" in t["name"])
        expression = task["ansible.builtin.assert"]["that"][0]
        for config, expected in [("hostname: jellyfin\n", "True"),
                                 ("hostname: jellyfin\n[backup]\n", "False")]:
            result = ENV.from_string("{{ " + expression + " }}").render(
                servarr_ct_mapping_changed=True,
                servarr_ct_config_file={"content": base64.b64encode(config.encode()).decode()},
                **task["vars"],
            )
            self.assertEqual(result, expected)

    def test_snapshot_mappings_do_not_make_an_unchanged_container_dirty(self):
        tasks = yaml.safe_load((ROOT / "roles/proxmox_lxc/tasks/container.yaml").read_text())
        idmap = next(t["ansible.builtin.set_fact"]["servarr_ct_idmap"] for t in tasks
                     if "servarr_ct_idmap" in t.get("ansible.builtin.set_fact", {}))
        rendered = ENV.from_string(idmap).render(
            servarr_uid=1500, servarr_gid=1500, servarr_lxc_idmap_base=100000,
        )
        source = next(t["ansible.builtin.set_fact"]["servarr_ct_mapping_changed"] for t in tasks
                      if "servarr_ct_mapping_changed" in t.get("ansible.builtin.set_fact", {}))
        config = f"hostname: radarr\n{rendered}\n[before-upgrade]\n{rendered}"
        result = ENV.from_string(source).render(
            servarr_ct_config_file={"content": base64.b64encode(config.encode()).decode()},
            servarr_ct_idmap=rendered,
        )
        self.assertEqual(result, "False")

    def test_mapping_covers_guest_ids_without_overlap(self):
        tasks = yaml.safe_load((ROOT / "roles/proxmox_lxc/tasks/container.yaml").read_text())
        source = next(t["ansible.builtin.set_fact"]["servarr_ct_idmap"] for t in tasks
                      if "servarr_ct_idmap" in t.get("ansible.builtin.set_fact", {}))
        for uid, gid in [(1500, 1500), (1000, 2000), (1, 65534)]:
            rendered = ENV.from_string(source).render(
                servarr_uid=uid, servarr_gid=gid, servarr_lxc_idmap_base=100000,
            )
            for identity, media_id in [("u", uid), ("g", gid)]:
                rows = [line.split()[2:] for line in rendered.splitlines()
                        if line.startswith(f"lxc.idmap: {identity} ")]
                mapping = {}
                host_ids = set()
                for row in rows:
                    guest, host, count = map(int, row)
                    for offset in range(count):
                        self.assertNotIn(guest + offset, mapping)
                        self.assertNotIn(host + offset, host_ids)
                        mapping[guest + offset] = host + offset
                        host_ids.add(host + offset)
                self.assertEqual(len(mapping), 65536)
                self.assertEqual(mapping[media_id], media_id)
                self.assertEqual(mapping[0], 100000)
                self.assertEqual(mapping[65535], 165535)

    def test_bind_mount_option_order_does_not_trigger_a_restart(self):
        tasks = yaml.safe_load((ROOT / "roles/proxmox_lxc/tasks/container.yaml").read_text())
        source = next(t["ansible.builtin.set_fact"]["servarr_ct_mount_matches"] for t in tasks
                      if "servarr_ct_mount_matches" in t.get("ansible.builtin.set_fact", {}))
        for mount in ["/opt/media,backup=0,mp=/opt/media", "/opt/media,mp=/opt/media,backup=0"]:
            result = ENV.from_string(source).render(
                servarr_ct_config={"mp0": mount}, servarr_host_media_dir="/opt/media", media_dir="/opt/media",
            )
            self.assertEqual(result.strip(), "True")
        result = ENV.from_string(source).render(
            servarr_ct_config={"mp0": "/opt/media,mp=/opt/media,ro=1"},
            servarr_host_media_dir="/opt/media", media_dir="/opt/media",
        )
        self.assertEqual(result.strip(), "False")


if __name__ == "__main__":
    unittest.main()
