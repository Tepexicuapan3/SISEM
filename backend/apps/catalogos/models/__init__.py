from .base import CatalogBase

from .areas import Areas
from .areas_clinicas import CatAreaClinica, CentroAreaClinica
from .autorizadores import Autorizadores
from .bajas import Bajas
from .calidad_laboral import CalidadLaboral
from .centros_atencion import CatCentroAtencion
from .centro_atencion_horario import CatCentroAtencionHorario
from .centro_atencion_excepcion import CatCentroAtencionExcepcion
from .cies import CatCies
from .cie9_mc import CatCie9Mc
from .consultorios import Consultorios
from .discapacidades import Discapacidades
from .edo_civil import EdoCivil
from .enfermedades import Enfermedades
from .escolaridad import Escolaridad
from .escuelas import Escuelas
from .tipo_personal import CatTipoPersonal
from .especialidades import Especialidades
from .estudios_medicos import EstudiosMed
from .grupos_medicamentos import GruposDeMedicamentos
from .medicamentos import Medicamentos
from .motivos_cita import MotivoCita
from .ocupaciones import Ocupaciones
from .origen_consulta import OrigenCons
from .parentescos import Parentesco
from .pases import Pases
from .religion import Religion

# ALIAS IMPORTANTES
from .roles import Roles
from .permisos import Permisos
from .roles import Roles as CatRol
from .permisos import Permisos as CatPermiso

from .sucursales import CatSucursal
from .tipos_areas import TiposAreas
from .tipos_autorizacion import TpAutorizacion
from .tipos_citas import TipoDeCitas
from .tipo_consulta import TipoConsulta
from .tipos_licencias import Licencias
from .tipo_residencia import TipoResidencia
from .tipos_sanguineo import TiposSanguineo
from .turnos import Turnos
from .vacunas import Vacunas



__all__ = [
    "CatalogBase",
    "Areas",
    "CatAreaClinica",
    "CentroAreaClinica",
    "Autorizadores",
    "Bajas",
    "CalidadLaboral",
    "CatCentroAtencion",
    "CatCentroAtencionHorario",
    "CatCentroAtencionExcepcion",
    "CatCies",
    "CatCie9Mc",
    "Consultorios",
    "Discapacidades",
    "EdoCivil",
    "Enfermedades",
    "Escolaridad",
    "Escuelas",
    "Especialidades",
    "EstudiosMed",
    "GruposDeMedicamentos",
    "Medicamentos",
    "MotivoCita",
    "Ocupaciones",
    "OrigenCons",
    "Parentesco",
    "Pases",
    "Religion",
    "Roles",
    "Permisos",
    "CatRol",
    "CatPermiso",
    "CatSucursal",
    "TiposAreas",
    "TpAutorizacion",
    "TipoDeCitas",
    "TipoConsulta",
    "TipoResidencia",
    "Licencias",
    "TiposSanguineo",
    "Turnos",
    "Vacunas",
    "CatCies",
    "CatTipoPersonal",
]
