"""
Caso de uso: alta de un usuario (SyUsuario + DetUsuario + RelUsuarioRol) con
password temporal y envio opcional de credenciales por correo.

Compartido por:
- `UsersListCreateView.post` (alta individual, en
  `apps/administracion/views/rbac_views.py`).
- El import masivo de usuarios por Excel (`UserImportConfirmView`, en
  `apps/administracion/views/user_import_views.py`).

Este caso de uso asume que TODAS las validaciones de negocio (unicidad de
usuario/correo, existencia de rol/clinica/etc.) ya se resolvieron antes de
llamarlo -- aca solo se persiste. `email` puede venir vacio/None: el correo
es opcional, y en ese caso NUNCA se intenta enviar el correo de
credenciales (no es un fallo, no dispara rollback -- eso lo decide quien
llama, ya que el rollback ante fallo de envio depende de
`settings.ALLOW_USER_CREATE_WITHOUT_EMAIL`, una decision de transporte/HTTP
que no le corresponde a este caso de uso).
"""

from dataclasses import dataclass, field
from typing import List, Optional

from django.contrib.auth.hashers import make_password
from django.db import transaction

from apps.administracion.models import RelUsuarioRol
from apps.administracion.use_cases.users.password_utils import (
    generate_temporary_password,
)
from apps.authentication.models import DetUsuario, DetUsuarioCedula, SyUsuario
from apps.authentication.services.email_service import send_user_credentials_email


@dataclass(frozen=True)
class CedulaInput:
    numero: str
    tipo: str
    es_principal: bool = False


@dataclass
class CreateUserData:
    username: str
    first_name: str
    paternal_name: str
    role: object  # apps.catalogos.models.Roles
    maternal_name: str = ""
    email: Optional[str] = None
    actor: Optional[SyUsuario] = None
    clinic: Optional[object] = None
    no_exp: Optional[str] = None
    cd_laboral: Optional[str] = None
    telefono: Optional[str] = None
    sexo: Optional[str] = None
    fecha_nac: Optional[object] = None
    area_clinica: Optional[object] = None
    escolaridad: Optional[object] = None
    escuela: Optional[object] = None
    tipo_personal: Optional[object] = None
    cedulas: List[CedulaInput] = field(default_factory=list)
    est_activo: bool = True
    # False para el import masivo: las credenciales se mandan despues en
    # batch (fuera de la transaccion), no una a una durante el alta -- ver
    # `import_users.ConfirmUsersImportUseCase`.
    send_credentials_email: bool = True
    # Credenciales ya generadas por quien llama (import masivo: hashea en
    # paralelo ANTES de abrir la transaccion, porque PBKDF2 ~0.5 s/usuario
    # es el cuello de botella). Si vienen en None se generan aqui como siempre.
    temporary_password: Optional[str] = None
    clave_hash: Optional[str] = None


@dataclass
class CreateUserResult:
    user: SyUsuario
    detail: DetUsuario
    temporary_password: str
    full_name: str
    # None => no se intento enviar (no habia correo). True/False => resultado real del envio.
    credentials_email_sent: Optional[bool]


class CreateUserUseCase:

    @staticmethod
    @transaction.atomic
    def execute(data: CreateUserData) -> CreateUserResult:
        if data.temporary_password and data.clave_hash:
            temporary_password = data.temporary_password
            clave_hash = data.clave_hash
        else:
            temporary_password = generate_temporary_password()
            clave_hash = make_password(temporary_password)
        correo = data.email or None

        user = SyUsuario.objects.create(
            usuario=data.username,
            correo=correo,
            clave_hash=clave_hash,
            est_activo=data.est_activo,
            est_bloqueado=False,
            cambiar_clave=True,
            terminos_acept=False,
            usr_alta=data.actor,
        )

        maternal_name = data.maternal_name or ""
        full_name = " ".join(
            part
            for part in [data.first_name, data.paternal_name, maternal_name]
            if part
        ).strip()

        detail = DetUsuario.objects.create(
            id_usuario=user,
            nombre=data.first_name,
            paterno=data.paternal_name,
            materno=maternal_name,
            id_centro_atencion=data.clinic,
            no_exp=data.no_exp or None,
            cd_laboral=data.cd_laboral or None,
            telefono=data.telefono or None,
            sexo=data.sexo or None,
            fecha_nac=data.fecha_nac or None,
            id_area_clinica=data.area_clinica,
            id_escolaridad=data.escolaridad,
            id_escuela=data.escuela,
            id_tipo_personal=data.tipo_personal,
        )

        RelUsuarioRol.objects.create(
            id_usuario=user,
            id_rol=data.role,
            is_primary=True,
            usr_asignacion=data.actor,
        )

        for idx, cedula in enumerate(data.cedulas):
            DetUsuarioCedula.objects.create(
                id_usuario=user,
                numero=cedula.numero,
                tipo=cedula.tipo,
                es_principal=cedula.es_principal,
                orden=idx + 1,
            )

        credentials_email_sent = None
        if correo and data.send_credentials_email:
            credentials_email_sent = send_user_credentials_email(
                recipient_email=correo,
                username=user.usuario,
                temporary_password=temporary_password,
                user_name=full_name or user.usuario,
            )

        return CreateUserResult(
            user=user,
            detail=detail,
            temporary_password=temporary_password,
            full_name=full_name,
            credentials_email_sent=credentials_email_sent,
        )
