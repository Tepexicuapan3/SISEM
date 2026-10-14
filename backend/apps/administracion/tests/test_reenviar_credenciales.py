"""Cobertura del comando `reenviar_credenciales` (correos de alta fallidos)."""

import io
from unittest.mock import patch

from django.contrib.auth.hashers import check_password, make_password
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.administracion.models import AuditoriaEvento, UserImportJob
from apps.authentication.models import DetUsuario, SyUsuario

SEND_BATCH = (
    "apps.administracion.management.commands.reenviar_credenciales."
    "send_user_credentials_email_batch"
)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ReenviarCredencialesTests(TestCase):
    def setUp(self):
        self.ana = self._user("ana")
        self.beto = self._user("beto")
        # Ya entró al sistema: no se le debe tocar la contraseña.
        self.carla = self._user("carla", last_conexion=timezone.now(), cambiar_clave=False)
        self.job = UserImportJob.objects.create(
            file_name="usuarios.xlsx", status=UserImportJob.Status.SUCCESS,
        )
        self.job.set_result({
            "emailFailures": [
                {"username": u.usuario, "email": u.correo}
                for u in (self.ana, self.beto, self.carla)
            ]
        })
        self.job.save()

    def _user(self, username, **fields):
        user = SyUsuario.objects.create(
            usuario=username,
            correo=f"{username}@example.com",
            clave_hash=make_password("original"),
            est_activo=True,
            cambiar_clave=fields.pop("cambiar_clave", True),
            **fields,
        )
        DetUsuario.objects.create(id_usuario=user, nombre=username.title(), paterno="Prueba")
        return user

    def _run(self, *args):
        out = io.StringIO()
        call_command("reenviar_credenciales", *args, stdout=out)
        return out.getvalue()

    def _job_failures(self):
        self.job.refresh_from_db()
        return [f["username"] for f in self.job.get_result()["emailFailures"]]

    def test_reenvia_a_los_fallidos_del_ultimo_job_y_omite_a_quien_ya_entro(self):
        with patch(SEND_BATCH, return_value={"sent": 2, "failed": []}) as send:
            output = self._run("--ultimo-job")

        (emails,), _ = send.call_args
        self.assertEqual([e["username"] for e in emails], ["ana", "beto"])
        # La contraseña enviada por correo es la que quedó guardada.
        self.ana.refresh_from_db()
        self.assertTrue(check_password(emails[0]["temporary_password"], self.ana.clave_hash))
        self.assertTrue(self.ana.cambiar_clave)
        self.assertEqual(emails[0]["user_name"], "Ana Prueba")
        # A quien ya entró no se le cambia la contraseña.
        self.carla.refresh_from_db()
        self.assertTrue(check_password("original", self.carla.clave_hash))
        self.assertIn("ya entró al sistema", output)
        # Enviados y "ya entró" salen de la lista del job.
        self.assertEqual(self._job_failures(), [])
        self.assertEqual(
            AuditoriaEvento.objects.filter(accion="RBAC_USER_CREDENTIALS_RESEND").count(), 2
        )

    def test_limite_reparte_el_envio_en_varias_corridas(self):
        with patch(SEND_BATCH, return_value={"sent": 1, "failed": []}) as send:
            self._run("--job", str(self.job.id), "--limite", "1")
        (emails,), _ = send.call_args
        self.assertEqual([e["username"] for e in emails], ["ana"])
        self.assertEqual(self._job_failures(), ["beto"])

        # La segunda corrida sigue con el que faltaba, sin repetir a "ana".
        with patch(SEND_BATCH, return_value={"sent": 1, "failed": []}) as send:
            self._run("--job", str(self.job.id), "--limite", "1")
        (emails,), _ = send.call_args
        self.assertEqual([e["username"] for e in emails], ["beto"])
        self.assertEqual(self._job_failures(), [])

    def test_correo_que_vuelve_a_fallar_queda_pendiente(self):
        failed = [{"username": "beto", "email": "beto@example.com"}]
        with patch(SEND_BATCH, return_value={"sent": 1, "failed": failed}):
            output = self._run("--ultimo-job")

        self.assertEqual(self._job_failures(), ["beto"])
        self.assertIn("volvieron a fallar: 1", output)
        evento = AuditoriaEvento.objects.get(
            accion="RBAC_USER_CREDENTIALS_RESEND", target_usuario=self.beto
        )
        self.assertEqual(evento.resultado, "FAIL")

    def test_dry_run_no_cambia_nada(self):
        with patch(SEND_BATCH) as send:
            output = self._run("--ultimo-job", "--dry-run")

        send.assert_not_called()
        self.ana.refresh_from_db()
        self.assertTrue(check_password("original", self.ana.clave_hash))
        self.assertEqual(self._job_failures(), ["ana", "beto", "carla"])
        self.assertIn("[dry-run] ana\tana@example.com", output)

    def test_por_lista_de_usuarios_omite_inexistentes_y_sin_correo(self):
        sin_correo = self._user("dani")
        SyUsuario.objects.filter(pk=sin_correo.pk).update(correo=None)

        with patch(SEND_BATCH, return_value={"sent": 1, "failed": []}) as send:
            output = self._run("--usuarios", "ana, fantasma ,dani")

        (emails,), _ = send.call_args
        self.assertEqual([e["username"] for e in emails], ["ana"])
        self.assertIn("Omitidos (no existe): 1", output)
        self.assertIn("Omitidos (sin correo): 1", output)

    def test_ultimo_job_sin_fallidos_avisa(self):
        self.job.set_result({"emailFailures": []})
        self.job.save()

        with self.assertRaisesMessage(CommandError, "correos fallidos pendientes"):
            self._run("--ultimo-job")
