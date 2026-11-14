"""Admin recovery contract tests with a fake Flask app/FAB manager; no real DB or secrets."""
import contextlib
import importlib.util
import io
from pathlib import Path
import secrets
import sys
import types
import unittest
from unittest.mock import Mock, patch

PATH = Path(__file__).resolve().parents[1] / 'airflow/init_user.py'
SPEC = importlib.util.spec_from_file_location('admin_helper', PATH)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.manager = Mock()
        self.user = types.SimpleNamespace(id=1, is_active=True, roles=[types.SimpleNamespace(name='Admin')])
        self.manager.find_user.return_value = self.user
        self.password = secrets.token_urlsafe(24)  # Synthetic, generated in memory; never output.
        self.stdout = io.StringIO()
        self.app = Mock()
        self.app.appbuilder.sm = self.manager
        self.app.app_context.return_value = contextlib.nullcontext()
        self.factory = Mock(return_value=self.app)
        airflow = types.ModuleType('airflow')
        www = types.ModuleType('airflow.www')
        app_module = types.ModuleType('airflow.www.app')
        app_module.cached_app = self.factory
        self.modules = {'airflow': airflow, 'airflow.www': www, 'airflow.www.app': app_module}

    def run_helper(self, arguments, inputs=None, matches=True, interactive=True):
        with patch.dict(sys.modules, self.modules), \
                patch.object(helper.sys.stdin, 'isatty', return_value=interactive), \
                patch.object(helper.getpass, 'getpass', side_effect=inputs or [self.password, self.password]), \
                patch.object(helper, 'password_matches', return_value=matches), \
                contextlib.redirect_stdout(self.stdout):
            result = helper.main(arguments)
        self.assertNotIn(self.password, self.stdout.getvalue())
        return result

    def test_reset_uses_one_initialized_app_and_supported_api(self):
        self.assertEqual(self.run_helper(['--reset-password', '--username', 'admin']), 0)
        self.factory.assert_called_once_with()
        self.app.app_context.assert_called_once_with()
        self.manager.reset_password.assert_called_once_with(self.user.id, self.password)
        self.manager.get_session.expire_all.assert_called_once_with()
        self.assertEqual(self.manager.find_user.call_count, 2)

    def test_check_does_not_reset_or_authenticate(self):
        self.assertEqual(self.run_helper(['--check-password']), 0)
        self.manager.reset_password.assert_not_called()
        self.manager.update_user.assert_not_called()
        self.manager.auth_user_db.assert_not_called()
        self.manager.add_user.assert_not_called()

    def test_wrong_password_is_failure_without_reset(self):
        self.assertEqual(self.run_helper(['--check-password'], matches=False), 1)
        self.manager.reset_password.assert_not_called()

    def test_password_mismatch_empty_or_noninteractive_never_opens_app(self):
        for arguments, inputs, interactive in [(['--reset-password'], [self.password, secrets.token_urlsafe(24)], True),
                                                (['--reset-password'], [''], True),
                                                (['--reset-password'], None, False)]:
            with self.subTest(arguments=arguments, interactive=interactive):
                self.assertEqual(self.run_helper(arguments, inputs, interactive=interactive), 1)
                self.factory.assert_not_called()

    def test_missing_inactive_and_nonadmin_users_are_not_changed(self):
        for user in [None, types.SimpleNamespace(is_active=False),
                     types.SimpleNamespace(is_active=True, roles=[])]:
            with self.subTest(user=user):
                self.manager.find_user.return_value = user
                self.assertEqual(self.run_helper(['--reset-password']), 1)
                self.manager.reset_password.assert_not_called()
                self.manager.add_user.assert_not_called()

    def test_reset_failure_rolls_back_and_sanitizes_exception(self):
        self.manager.reset_password.side_effect = AssertionError(self.password)
        self.assertEqual(self.run_helper(['--reset-password']), 1)
        self.manager.get_session.rollback.assert_called_once_with()
        self.assertIn('AssertionError', self.stdout.getvalue())
        self.assertNotIn('PASS:', self.stdout.getvalue())

    def test_api_false_or_failed_recheck_does_not_claim_success(self):
        self.manager.reset_password.return_value = False
        self.assertEqual(self.run_helper(['--reset-password']), 1)
        self.manager.reset_password.return_value = True
        self.assertEqual(self.run_helper(['--reset-password'], matches=False), 1)
        self.assertNotIn('PASS:', self.stdout.getvalue())

    def test_initialize_keeps_existing_password_unchanged(self):
        with patch.dict(helper.os.environ, {'AIRFLOW_ADMIN_PASSWORD': self.password,
                                           'AIRFLOW__WEBSERVER__SECRET_KEY': secrets.token_urlsafe(32)}):
            self.assertEqual(self.run_helper([]), 0)
        self.manager.reset_password.assert_not_called()
        self.manager.add_user.assert_not_called()


if __name__ == '__main__':
    unittest.main()
