import unittest
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from apartment_agents.app.errors import AdkRuntimeUnavailableError, ConfigValidationError
from apartment_agents.adk.runner import validate_runner_startup
from apartment_agents.config import AppConfig


class AppConfigTest(unittest.TestCase):
    def test_mock_backend_does_not_require_google_api_key(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = AppConfig(output_dir=Path(tmpdir), adk_backend="mock")
            self.assertEqual(config.adk_backend, "mock")
            self.assertEqual(config.workspace_dir, Path(tmpdir) / "workspace")
            self.assertTrue(config.workspace_dir.exists())

    def test_workspace_dir_can_be_loaded_from_env(self) -> None:
        with TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir) / "custom-workspace"
            with patch.dict(
                "os.environ",
                {
                    "REPORT_OUTPUT_DIR": str(Path(tmpdir) / "reports"),
                    "BOLIGMESTER_WORKSPACE_DIR": str(workspace_dir),
                },
                clear=False,
            ):
                config = AppConfig.load()

            self.assertEqual(config.workspace_dir, workspace_dir)
            self.assertTrue(workspace_dir.exists())

    def test_google_adk_backend_requires_google_api_key(self) -> None:
        with TemporaryDirectory() as tmpdir:
            with self.assertRaises(ConfigValidationError):
                AppConfig(output_dir=Path(tmpdir), adk_backend="google_adk", google_api_key=None)

    def test_google_adk_startup_validation_fails_when_runtime_missing(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = AppConfig(
                output_dir=Path(tmpdir),
                adk_backend="google_adk",
                google_api_key="test-key",
            )
            try:
                import_module("google.adk")  # pragma: no cover
            except Exception:
                with self.assertRaises(AdkRuntimeUnavailableError):
                    validate_runner_startup(config)

    def test_google_adk_startup_validation_accepts_installed_runtime(self) -> None:
        try:
            import_module("google.adk")
        except Exception:
            self.skipTest("google-adk is not installed")

        with TemporaryDirectory() as tmpdir:
            config = AppConfig(
                output_dir=Path(tmpdir),
                adk_backend="google_adk",
                google_api_key="test-key",
            )

            validate_runner_startup(config)

    def test_browser_listing_fetch_requires_command_when_enabled(self) -> None:
        with TemporaryDirectory() as tmpdir:
            with self.assertRaises(ConfigValidationError):
                AppConfig(
                    output_dir=Path(tmpdir),
                    adk_backend="mock",
                    enable_browser_listing_fetch=True,
                )

    def test_browser_listing_fetch_command_requires_url_placeholder(self) -> None:
        with TemporaryDirectory() as tmpdir:
            with self.assertRaises(ConfigValidationError):
                AppConfig(
                    output_dir=Path(tmpdir),
                    adk_backend="mock",
                    browser_listing_fetch_command="python3 script.py",
                )

    def test_browser_storage_state_path_must_exist(self) -> None:
        with TemporaryDirectory() as tmpdir:
            with self.assertRaises(ConfigValidationError):
                AppConfig(
                    output_dir=Path(tmpdir),
                    adk_backend="mock",
                    browser_storage_state_path=Path(tmpdir) / "missing.json",
                )


if __name__ == "__main__":
    unittest.main()
