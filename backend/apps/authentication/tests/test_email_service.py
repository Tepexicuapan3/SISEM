from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.authentication.services.email_service import (
    send_reset_code_email,
    send_user_credentials_email,
)


class EmailServiceTests(SimpleTestCase):
    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="",
        EMAIL_HOST_USER="",
        EMAIL_HOST_PASSWORD="",
    )
    def test_returns_true_when_smtp_not_configured(self):
        result = send_reset_code_email("user@example.com", "123456", user_name="User")

        self.assertTrue(result)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        EMAIL_HOST_USER="mailer@example.com",
        EMAIL_HOST_PASSWORD="secret",
        DEFAULT_FROM_EMAIL="mailer@example.com",
    )
    @patch("apps.authentication.services.email_service.send_mail")
    @patch("apps.authentication.services.email_service.render_to_string")
    def test_sends_email_when_smtp_is_configured(self, render_mock, send_mail_mock):
        render_mock.return_value = "<html>ok</html>"
        send_mail_mock.return_value = 1

        result = send_reset_code_email("user@example.com", "123456", user_name="User")

        self.assertTrue(result)
        send_mail_mock.assert_called_once()

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        EMAIL_HOST_USER="mailer@example.com",
        EMAIL_HOST_PASSWORD="secret",
        DEFAULT_FROM_EMAIL="mailer@example.com",
    )
    @patch("apps.authentication.services.email_service.send_mail")
    @patch("apps.authentication.services.email_service.render_to_string")
    def test_returns_false_when_send_mail_fails(self, render_mock, send_mail_mock):
        render_mock.return_value = "<html>ok</html>"
        send_mail_mock.side_effect = RuntimeError("smtp down")

        result = send_reset_code_email("user@example.com", "123456", user_name="User")

        self.assertFalse(result)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="",
        EMAIL_HOST_USER="",
        EMAIL_HOST_PASSWORD="",
    )
    def test_credentials_email_returns_false_when_smtp_not_configured(self):
        result = send_user_credentials_email(
            "user@example.com",
            username="new_user",
            temporary_password="TempPass_123456!",
            user_name="User",
        )

        self.assertFalse(result)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        EMAIL_HOST_USER="mailer@example.com",
        EMAIL_HOST_PASSWORD="secret",
        DEFAULT_FROM_EMAIL="mailer@example.com",
    )
    @patch("apps.authentication.services.email_service.send_mail")
    @patch("apps.authentication.services.email_service.render_to_string")
    def test_credentials_email_sends_when_smtp_is_configured(
        self, render_mock, send_mail_mock
    ):
        render_mock.return_value = "<html>ok</html>"
        send_mail_mock.return_value = 1

        result = send_user_credentials_email(
            "user@example.com",
            username="new_user",
            temporary_password="TempPass_123456!",
            user_name="User",
        )

        self.assertTrue(result)
        send_mail_mock.assert_called_once()

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        EMAIL_HOST_USER="mailer@example.com",
        EMAIL_HOST_PASSWORD="secret",
        DEFAULT_FROM_EMAIL="mailer@example.com",
    )
    @patch("apps.authentication.services.email_service.send_mail")
    @patch("apps.authentication.services.email_service.render_to_string")
    def test_credentials_email_returns_false_when_send_mail_fails(
        self, render_mock, send_mail_mock
    ):
        render_mock.return_value = "<html>ok</html>"
        send_mail_mock.side_effect = RuntimeError("smtp down")

        result = send_user_credentials_email(
            "user@example.com",
            username="new_user",
            temporary_password="TempPass_123456!",
            user_name="User",
        )

        self.assertFalse(result)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        EMAIL_HOST_USER="mailer@example.com",
        EMAIL_HOST_PASSWORD="secret",
        DEFAULT_FROM_EMAIL="mailer@example.com",
        SISEM_LOGIN_URL="https://sisem.example.com/login",
        SISEM_SUPPORT_EMAIL="soporte@sisem.example.com",
    )
    @patch("apps.authentication.services.email_service.send_mail")
    @patch("apps.authentication.services.email_service.render_to_string")
    def test_credentials_email_prefers_sisem_aliases(self, render_mock, send_mail_mock):
        render_mock.return_value = "<html>ok</html>"
        send_mail_mock.return_value = 1

        result = send_user_credentials_email(
            "user@example.com",
            username="new_user",
            temporary_password="TempPass_123456!",
            user_name="User",
        )

        self.assertTrue(result)
        subject, message = send_mail_mock.call_args.args[0:2]
        self.assertEqual(subject, "Credenciales de acceso a SISEM")
        self.assertIn("cuenta de SISEM", message)
        self.assertIn("https://sisem.example.com/login", message)
        self.assertIn("soporte@sisem.example.com", message)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        EMAIL_HOST_USER="mailer@example.com",
        EMAIL_HOST_PASSWORD="secret",
        DEFAULT_FROM_EMAIL="mailer@example.com",
        SISEM_LOGIN_URL="https://sisem.example.com/login",
        SISEM_SUPPORT_EMAIL="soporte@sisem.example.com",
    )
    @patch("apps.authentication.services.email_service.send_mail")
    @patch("apps.authentication.services.email_service.render_to_string")
    def test_credentials_email_uses_sisem_aliases(self, render_mock, send_mail_mock):
        render_mock.return_value = "<html>ok</html>"
        send_mail_mock.return_value = 1

        result = send_user_credentials_email(
            "user@example.com",
            username="new_user",
            temporary_password="TempPass_123456!",
            user_name="User",
        )

        self.assertTrue(result)
        _, message = send_mail_mock.call_args.args[0:2]
        self.assertIn("https://sisem.example.com/login", message)
        self.assertIn("soporte@sisem.example.com", message)


class _FlakyConnection:
    """Conexion SMTP falsa que se cae tras `fail_after` mensajes enviados."""

    instances = []

    def __init__(self, fail_after=None):
        self.fail_after = fail_after
        self.sent = 0
        _FlakyConnection.instances.append(self)

    def open(self):
        return True

    def close(self):
        return None

    def send_messages(self, messages):
        if self.fail_after is not None and self.sent >= self.fail_after:
            raise ConnectionError("SMTP server disconnected")
        self.sent += len(messages)
        return len(messages)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@patch("apps.authentication.services.email_service.render_to_string", return_value="<p>x</p>")
class CredentialsBatchTests(SimpleTestCase):
    USERS = [
        {"email": f"u{i}@example.com", "username": f"u{i}", "temporary_password": "T", "user_name": "U"}
        for i in range(5)
    ]

    def setUp(self):
        _FlakyConnection.instances = []

    def test_reconnects_when_smtp_drops_mid_batch(self, _render_mock):
        # Primera conexion se cae tras 2 mensajes; la reconexion manda el resto.
        factory = iter([_FlakyConnection(fail_after=2), _FlakyConnection()])
        with patch(
            "apps.authentication.services.email_service.get_connection",
            side_effect=lambda: next(factory),
        ):
            from apps.authentication.services.email_service import send_user_credentials_email_batch

            result = send_user_credentials_email_batch(self.USERS)

        self.assertEqual(result, {"sent": 5, "failed": []})
        self.assertEqual(_FlakyConnection.instances[1].sent, 3)

    def test_reports_progress_for_every_user(self, _render_mock):
        progress = []
        with patch(
            "apps.authentication.services.email_service.get_connection",
            side_effect=lambda: _FlakyConnection(),
        ):
            from apps.authentication.services.email_service import send_user_credentials_email_batch

            send_user_credentials_email_batch(self.USERS, on_progress=progress.append)

        self.assertEqual(progress, [1, 2, 3, 4, 5])

    def test_marks_failed_when_retry_also_fails(self, _render_mock):
        with patch(
            "apps.authentication.services.email_service.get_connection",
            side_effect=lambda: _FlakyConnection(fail_after=0),
        ):
            from apps.authentication.services.email_service import send_user_credentials_email_batch

            result = send_user_credentials_email_batch(self.USERS[:2])

        self.assertEqual(result["sent"], 0)
        self.assertEqual([f["username"] for f in result["failed"]], ["u0", "u1"])
