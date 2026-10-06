"""Offline API contract and idempotency tests for the Jellyfin bootstrap."""
import copy
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from test_lxc import ENV, ROOT


class JellyfinTests(unittest.TestCase):
    def setUp(self):
        script = ENV.from_string(
            (ROOT / "roles/servarr/templates/bootstrap-jellyfin.py.j2").read_text()
        ).render(
            servarr_endpoints={"jellyfin": "192.0.2.6", "jellyseerr": "192.0.2.5",
                               "radarr": "192.0.2.1", "sonarr": "192.0.2.2"},
            servarr_ports={"jellyfin": 8096, "jellyseerr": 5055, "radarr": 7878, "sonarr": 8989},
            jellyfin_server_name="Homelab", radarr_root_folder="/opt/media/movies",
            sonarr_root_folder="/opt/media/tv", jellyfin_transcode_dir="/opt/media/transcodes/jellyfin",
            jellyfin_nvidia_enabled=True, jellyfin_nvidia_decoding_codecs=["h264", "hevc"],
            jellyseerr_admin_email="admin@example.test",
            jellyseerr_radarr_quality_profile_name="HD-1080p", jellyseerr_sonarr_quality_profile_name="HD-1080p",
        )
        self.module = {"__name__": "fixture"}
        exec(compile(script, "bootstrap-jellyfin.py", "exec"), self.module)
        self.credentials = {"jellyfin_admin_username": "admin", "jellyfin_admin_password": "fixture-secret",
                            "jellyseerr_api_key": "fixture-api-key", "radarr_api_key": "radarr-key",
                            "sonarr_api_key": "sonarr-key"}
        self.info = {"StartupWizardCompleted": False}
        self.folders = []
        self.encoding = {"H264Crf": 23}
        self.public = {"mediaServerType": 4, "initialized": False}
        self.settings = {"ip": "", "apiKey": "", "libraries": []}
        self.writes = []
        self.services = {"radarr": [], "sonarr": []}
        self.first_user = {"Name": "root"}
        fixture = self

        class FakeAPI:
            def __init__(self, base, headers=None):
                self.base, self.headers = base, headers or {}

            def request(self, path, data=None, method=None):
                if data is not None or "?sync" in path:
                    fixture.writes.append((path, copy.deepcopy(data)))
                if path == "/System/Info/Public":
                    return fixture.info
                if path == "/Startup/Complete":
                    fixture.info["StartupWizardCompleted"] = True
                    return None
                if path == "/Startup/User":
                    if data is not None:
                        fixture.first_user.update(data)
                    return fixture.first_user
                if path.startswith("/Startup/"):
                    return {}
                if path == "/Users/AuthenticateByName":
                    # Authentication is not a persistent config write.
                    fixture.writes.pop()
                    return {"AccessToken": "temporary-token", "User": {"Policy": {"IsAdministrator": True}}}
                if path == "/Library/VirtualFolders":
                    if 'Token="temporary-token"' not in self.headers.get("Authorization", ""):
                        raise AssertionError("Jellyfin requires its token in the preferred Authorization header")
                    return fixture.folders
                if path.startswith("/Library/VirtualFolders?"):
                    fixture.folders.append({"Name": "library", "ItemId": str(len(fixture.folders) + 1),
                                            "Locations": [data["LibraryOptions"]["PathInfos"][0]["Path"]]})
                    return None
                if path == "/System/Configuration/encoding":
                    if data is not None:
                        fixture.encoding.update(data)
                    return copy.deepcopy(fixture.encoding)
                if path == "/api/v1/settings/public":
                    return fixture.public
                if path == "/api/v1/settings/jellyfin":
                    if fixture.public["mediaServerType"] == 4:
                        raise AssertionError("Protected settings read before first administrator exists")
                    return fixture.settings
                if path == "/api/v1/auth/jellyfin":
                    fixture.public["mediaServerType"] = 2
                    fixture.settings.update({"ip": data["hostname"], "port": data["port"], "apiKey": "managed-token"})
                    return {}
                if path.startswith("/api/v1/settings/jellyfin/library?"):
                    fixture.settings["libraries"] = [{"id": f["ItemId"], "enabled": True} for f in fixture.folders]
                    return fixture.settings["libraries"]
                if path == "/api/v1/settings/initialize":
                    fixture.public["initialized"] = True
                    return fixture.public
                if path == "/api/v1/settings/jellyfin/users":
                    return [{"id": "admin-id", "username": "admin"}]
                if path == "/api/v3/qualityprofile":
                    return [{"id": 1, "name": "Any"}, {"id": 4, "name": "HD-1080p"}]
                if path in ("/api/v1/settings/radarr", "/api/v1/settings/sonarr"):
                    app = path.rsplit("/", 1)[1]
                    if data is not None:
                        fixture.services[app].append(copy.deepcopy(data))
                    return fixture.services[app]
                raise AssertionError(path)

        self.module["API"] = FakeAPI

    def test_first_run_then_unchanged_rerun(self):
        self.assertTrue(self.module["bootstrap"](self.credentials))
        self.assertEqual(self.encoding["HardwareAccelerationType"], "nvenc")
        self.assertEqual(self.encoding["H264Crf"], 23)
        self.assertEqual(self.encoding["TranscodingTempPath"], "/opt/media/transcodes/jellyfin")
        self.assertEqual(len(self.folders), 2)
        for app in ["radarr", "sonarr"]:
            self.assertEqual(self.services[app][0]["activeProfileName"], "HD-1080p")
            self.assertEqual(self.services[app][0]["activeProfileId"], 4)
        count = len(self.writes)
        self.assertFalse(self.module["bootstrap"](self.credentials))
        self.assertEqual(len(self.writes), count)

    def test_preserve_unrelated_libraries_and_encoding_settings(self):
        self.folders.append({"Name": "Family", "ItemId": "family", "Locations": ["/family"]})
        self.module["bootstrap"](self.credentials)
        self.assertEqual(len(self.folders), 3)
        self.assertEqual(self.encoding["H264Crf"], 23)

    def test_existing_other_media_server_is_not_overwritten(self):
        self.public["mediaServerType"] = 2
        self.settings.update({"ip": "192.0.2.99", "port": 8096, "apiKey": "keep-token"})
        with self.assertRaisesRegex(RuntimeError, "another media server"):
            self.module["bootstrap"](self.credentials)
        self.assertEqual(self.settings["apiKey"], "keep-token")

    def test_transport_errors_do_not_echo_credentials(self):
        # Recompile to test the real transport rather than the fake API.
        source = (ROOT / "roles/servarr/templates/bootstrap-jellyfin.py.j2").read_text()
        api_source = source[source.index("class API:"):source.index("def bootstrap(")]
        exec(api_source, self.module)
        error = HTTPError("http://example.test?secret=fixture-secret", 401, "fixture-secret", {}, None)
        with patch.dict(self.module, {"urlopen": unittest.mock.Mock(side_effect=error)}):
            with self.assertRaisesRegex(RuntimeError, "HTTP 401") as caught:
                self.module["API"]("http://example.test").request("/login?secret=fixture-secret", self.credentials)
        self.assertNotIn("fixture-secret", str(caught.exception))

    def test_do_not_migrate_existing_plex_server(self):
        self.public["mediaServerType"] = 1
        with self.assertRaisesRegex(RuntimeError, "different media server type"):
            self.module["bootstrap"](self.credentials)

    def test_preserve_existing_jellyseerr_service_choices(self):
        custom = {"name": "Custom Radarr", "activeProfileName": "Any", "activeProfileId": 1}
        self.services["radarr"].append(custom.copy())
        self.module["bootstrap"](self.credentials)
        self.assertEqual(self.services["radarr"], [custom])

    def test_resume_partial_startup_without_resetting_password(self):
        self.first_user = {"Name": "admin"}
        self.module["bootstrap"](self.credentials)
        self.assertFalse(any(path == "/Startup/User" and data is not None for path, data in self.writes))
