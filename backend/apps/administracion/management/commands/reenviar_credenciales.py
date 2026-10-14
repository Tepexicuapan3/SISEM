"""
Reenvía credenciales (contraseña temporal NUEVA por correo) a usuarios cuyo
correo de alta no salió -- típicamente los `emailFailures` de un import
masivo de usuarios.

La contraseña temporal original no se puede recuperar (solo existe el hash),
así que se genera una nueva, se guarda y se manda por correo. Por seguridad
SOLO se tocan usuarios que nunca entraron al sistema (`last_conexion` NULL) y
siguen con `cambiar_clave=True`: a quien ya entró no se le cambia nada.

Con `--job`/`--ultimo-job` el progreso se guarda en el propio job: los que
se envían bien salen de su lista de `emailFailures`, así que correr el mismo
comando otro día (p. ej. por el tope diario del servidor de correo, ver
`--limite`) continúa con los que faltan sin reenviar a nadie dos veces.

Uso típico en el servidor:
    docker compose exec backend python manage.py reenviar_credenciales --ultimo-job --dry-run
    docker compose exec backend python manage.py reenviar_credenciales --ultimo-job --limite 400
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.administracion.models import AuditoriaEvento, UserImportJob
from apps.administracion.use_cases.users.import_users import _hash_credentials
from apps.authentication.models import SyUsuario
from apps.authentication.services.email_service import send_user_credentials_email_batch

AUDIT_ACTION = "RBAC_USER_CREDENTIALS_RESEND"

SKIP_NO_EXISTE = "no existe"
SKIP_INACTIVO = "inactivo o bloqueado"
SKIP_SIN_CORREO = "sin correo"
SKIP_YA_ENTRO = "ya entró al sistema o ya cambió su contraseña"


def _noop_progress(phase, done, total):
    return None


def _full_name(user) -> str:
    det = getattr(user, "detalle", None)
    parts = [det.nombre, det.paterno, det.materno] if det else []
    return " ".join(p for p in parts if p).strip() or user.usuario


class Command(BaseCommand):
    help = (
        "Reenvía credenciales (contraseña temporal nueva por correo) a usuarios "
        "cuyo correo de alta falló. Solo toca usuarios que nunca entraron al "
        "sistema. --dry-run solo muestra a quién se enviaría."
    )

    def add_arguments(self, parser):
        origen = parser.add_mutually_exclusive_group(required=True)
        origen.add_argument("--job", help="ID (UUID) del import de usuarios con correos fallidos.")
        origen.add_argument(
            "--ultimo-job", action="store_true",
            help="Usa el import de usuarios más reciente que tenga correos fallidos.",
        )
        origen.add_argument("--usuarios", help="Logins separados por coma.")
        origen.add_argument(
            "--archivo",
            help="Archivo con un login por línea (acepta la salida 'login<TAB>correo' "
                 "de importar_usuarios_excel).",
        )
        parser.add_argument(
            "--limite", type=int, default=None,
            help="Máximo de correos a enviar en esta corrida (tope diario del servidor de correo).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Solo muestra a quién se enviaría. No cambia contraseñas ni manda correos.",
        )

    def handle(self, *args, **options):
        job = self._resolve_job(options)
        usernames = self._resolve_usernames(options, job)
        if not usernames:
            self.stdout.write(self.style.SUCCESS("No hay usuarios pendientes de reenvío."))
            return

        eligible, skipped = self._classify(usernames)
        limite = options["limite"]
        batch = eligible[:limite] if limite else eligible
        pendientes = eligible[len(batch):]

        self.stdout.write(f"Usuarios en la lista: {len(usernames)}")
        self.stdout.write(f"  Para enviar en esta corrida: {len(batch)}")
        if pendientes:
            self.stdout.write(f"  Quedan para otra corrida (--limite): {len(pendientes)}")
        self._print_skipped(skipped)

        if options["dry_run"]:
            for user in batch:
                self.stdout.write(f"  [dry-run] {user.usuario}\t{user.correo}")
            self.stdout.write(self.style.SUCCESS("[dry-run] No se cambió nada."))
            return

        # Quien ya entró al sistema no necesita reenvío: sale de la lista del job.
        ya_resueltos = set(skipped.get(SKIP_YA_ENTRO, []))
        if not batch:
            if job is not None and ya_resueltos:
                self._update_job_failures(job, ya_resueltos)
            return

        self.stdout.write("Generando contraseñas temporales (puede tardar unos minutos)...")
        credentials = _hash_credentials(len(batch), _noop_progress)
        self._save_passwords(batch, credentials)

        self.stdout.write(f"Enviando {len(batch)} correos...")
        result = send_user_credentials_email_batch(
            [
                {
                    "email": user.correo,
                    "username": user.usuario,
                    "temporary_password": temporary_password,
                    "user_name": _full_name(user),
                }
                for user, (temporary_password, _hash) in zip(batch, credentials)
            ]
        )
        failed_usernames = {f["username"] for f in result["failed"]}
        self._audit(batch, failed_usernames)

        if job is not None:
            sent = {user.usuario for user in batch} - failed_usernames
            self._update_job_failures(job, sent | ya_resueltos)

        self.stdout.write(self.style.SUCCESS(f"Correos enviados: {result['sent']}"))
        if result["failed"]:
            self.stdout.write(self.style.WARNING(
                f"Correos que volvieron a fallar: {len(result['failed'])} "
                "(su contraseña ya se cambió; vuelve a correr el comando para reintentar)"
            ))
            for failure in result["failed"]:
                self.stdout.write(f"  {failure['username']}\t{failure['email']}")
        if pendientes:
            self.stdout.write(
                f"Pendientes para otra corrida: {len(pendientes)}. "
                "Vuelve a correr el mismo comando para continuar."
            )

    # ── Origen de la lista ──────────────────────────────────────────────────

    def _resolve_job(self, options):
        if options["job"]:
            job = UserImportJob.objects.filter(id=options["job"]).first()
            if job is None:
                raise CommandError(f"No existe el import {options['job']}.")
            return job
        if options["ultimo_job"]:
            for job in UserImportJob.objects.filter(
                status=UserImportJob.Status.SUCCESS
            ).order_by("-fch_alta"):
                if (job.get_result() or {}).get("emailFailures"):
                    return job
            raise CommandError("Ningún import de usuarios tiene correos fallidos pendientes.")
        return None

    def _resolve_usernames(self, options, job) -> list[str]:
        if job is not None:
            failures = (job.get_result() or {}).get("emailFailures") or []
            raw = [f.get("username") for f in failures]
        elif options["usuarios"]:
            raw = options["usuarios"].split(",")
        else:
            try:
                with open(options["archivo"], encoding="utf-8") as fh:
                    # "login<TAB>correo" (salida de importar_usuarios_excel) o solo "login".
                    raw = [line.split("\t")[0] for line in fh]
            except FileNotFoundError as exc:
                raise CommandError(f"No existe el archivo: {options['archivo']}") from exc
        seen, usernames = set(), []
        for name in (r.strip() for r in raw if r):
            if name and name not in seen:
                seen.add(name)
                usernames.append(name)
        return usernames

    def _classify(self, usernames):
        users = {
            u.usuario: u
            for u in SyUsuario.objects.select_related("detalle").filter(usuario__in=usernames)
        }
        eligible, skipped = [], {}
        for name in usernames:
            user = users.get(name)
            if user is None:
                reason = SKIP_NO_EXISTE
            elif not user.est_activo or user.est_bloqueado:
                reason = SKIP_INACTIVO
            elif not user.correo:
                reason = SKIP_SIN_CORREO
            elif user.last_conexion is not None or not user.cambiar_clave:
                reason = SKIP_YA_ENTRO
            else:
                eligible.append(user)
                continue
            skipped.setdefault(reason, []).append(name)
        return eligible, skipped

    def _print_skipped(self, skipped):
        for reason, names in skipped.items():
            self.stdout.write(self.style.WARNING(f"  Omitidos ({reason}): {len(names)}"))
            for name in names:
                self.stdout.write(f"    {name}")

    # ── Escrituras ──────────────────────────────────────────────────────────

    @transaction.atomic
    def _save_passwords(self, batch, credentials):
        now = timezone.now()
        for user, (_temporary_password, clave_hash) in zip(batch, credentials):
            user.clave_hash = clave_hash
            user.cambiar_clave = True
            user.fch_modf = now
        SyUsuario.objects.bulk_update(batch, ["clave_hash", "cambiar_clave", "fch_modf"])

    def _audit(self, batch, failed_usernames):
        # Nunca se registra la contraseña: solo si el correo salió o no.
        AuditoriaEvento.objects.bulk_create(
            [
                AuditoriaEvento(
                    fch_evento=timezone.now(),
                    request_id="",
                    accion=AUDIT_ACTION,
                    recurso_tipo="user",
                    recurso_id=user.id_usuario,
                    resultado="FAIL" if user.usuario in failed_usernames else "SUCCESS",
                    codigo_error="EMAIL_SEND_FAILED" if user.usuario in failed_usernames else None,
                    target_usuario=user,
                    meta={"module": "administracion", "source": "reenviar_credenciales"},
                )
                for user in batch
            ]
        )

    def _update_job_failures(self, job, resolved_usernames):
        # Quita de emailFailures a los resueltos (correo enviado o ya entraron
        # al sistema); quedan los que volvieron a fallar, los no procesados por
        # --limite y los omitidos sin solución por reenvío (sin correo, inactivo).
        result = job.get_result() or {}
        result["emailFailures"] = [
            f for f in result.get("emailFailures") or []
            if f.get("username") not in resolved_usernames
        ]
        job.set_result(result)
        UserImportJob.objects.filter(id=job.id).update(result_json=job.result_json)
