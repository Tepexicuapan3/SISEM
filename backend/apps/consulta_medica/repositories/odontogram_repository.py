from django.utils import timezone

from apps.catalogos.models import CatEstadoPieza
from apps.consulta_medica.models import Odontogram, OdontogramToothState

_DECIDUOUS_QUADRANTS = "5678"


class OdontogramRepository:
    @staticmethod
    def latest_for_patient(no_exp, pk_num):
        return (
            Odontogram.objects.filter(no_exp=no_exp, pk_num=pk_num)
            .order_by("-created_at", "-id_odontogram")
            .first()
        )

    @staticmethod
    def get_version(no_exp, pk_num, version_id):
        return Odontogram.objects.filter(
            no_exp=no_exp, pk_num=pk_num, id_odontogram=version_id,
        ).first()

    @staticmethod
    def list_versions(no_exp, pk_num):
        return Odontogram.objects.filter(no_exp=no_exp, pk_num=pk_num).order_by(
            "-created_at", "-id_odontogram",
        )

    @staticmethod
    def states_by_tooth(odontogram):
        """{tooth_fdi: {face: OdontogramToothState}}."""
        result = {}
        if odontogram is None:
            return result
        for state in odontogram.teeth.select_related("state").all():
            result.setdefault(state.tooth_id, {})[state.face] = state
        return result

    @staticmethod
    def version_for_change(*, no_exp, pk_num, visit_id, actor_id):
        """
        Version a modificar: una por consulta. Se reutiliza la ultima si es de
        la misma visita (o, sin visita, si es una captura del mismo dia sin
        visita). Si no, se crea una nueva copiando el estado anterior -- el
        historial nunca se pisa.
        """
        latest = OdontogramRepository.latest_for_patient(no_exp, pk_num)
        if latest is not None and latest.origin == Odontogram.Origin.CAPTURE:
            same_visit = visit_id is not None and latest.visit_id == visit_id
            same_day_without_visit = (
                visit_id is None
                and latest.visit_id is None
                and timezone.localdate(latest.created_at) == timezone.localdate()
            )
            if same_visit or same_day_without_visit:
                return latest

        from apps.consulta_medica.repositories.stomatology_history_repository import (
            StomatologyHistoryRepository,
        )

        # ODONTOGRAMA cuelga de HC_ESTOMATOLOGIA (documento 5.3).
        section, _ = StomatologyHistoryRepository.get_or_create_for_patient(no_exp, pk_num)
        version = Odontogram.objects.create(
            no_exp=no_exp,
            pk_num=pk_num,
            stomatology_history=section,
            visit_id=visit_id,
            dentition=latest.dentition if latest else Odontogram.Dentition.PERMANENT,
            dmft_decayed=latest.dmft_decayed if latest else 0,
            dmft_missing=latest.dmft_missing if latest else 0,
            dmft_filled=latest.dmft_filled if latest else 0,
            dmft_total=latest.dmft_total if latest else 0,
            origin=Odontogram.Origin.CAPTURE,
            created_by_id=actor_id,
        )
        if latest is not None:
            OdontogramToothState.objects.bulk_create([
                OdontogramToothState(
                    odontogram=version, tooth_id=state.tooth_id, face=state.face,
                    state_id=state.state_id, observation=state.observation,
                )
                for state in latest.teeth.all()
            ])
        return version

    @staticmethod
    def upsert_state(odontogram, *, tooth_fdi, face, state, observation):
        tooth_state, _ = OdontogramToothState.objects.update_or_create(
            odontogram=odontogram,
            tooth_id=tooth_fdi,
            face=face,
            defaults={"state": state, "observation": observation},
        )
        return tooth_state

    @staticmethod
    def recompute(odontogram):
        """Recalcula CPOD (por PIEZA, no por cara: P > C > O) y denticion."""
        components_by_tooth = {}
        for tooth_id, component in odontogram.teeth.values_list("tooth_id", "state__dmft_component"):
            components_by_tooth.setdefault(tooth_id, set()).add(component)

        counts = {"C": 0, "P": 0, "O": 0}
        for components in components_by_tooth.values():
            for component in ("P", "C", "O"):
                if component in components:
                    counts[component] += 1
                    break

        teeth = components_by_tooth.keys()
        deciduous = any(fdi[0] in _DECIDUOUS_QUADRANTS for fdi in teeth)
        permanent = any(fdi[0] not in _DECIDUOUS_QUADRANTS for fdi in teeth)
        if deciduous and permanent:
            odontogram.dentition = Odontogram.Dentition.MIXED
        elif deciduous:
            odontogram.dentition = Odontogram.Dentition.DECIDUOUS
        else:
            odontogram.dentition = Odontogram.Dentition.PERMANENT
        odontogram.dmft_decayed = counts["C"]
        odontogram.dmft_missing = counts["P"]
        odontogram.dmft_filled = counts["O"]
        odontogram.dmft_total = counts["C"] + counts["P"] + counts["O"]
        odontogram.save(update_fields=["dentition", "dmft_decayed", "dmft_missing", "dmft_filled", "dmft_total"])
        return odontogram

    @staticmethod
    def active_state_by_code(code):
        return CatEstadoPieza.objects.filter(code=code, is_active=True).first()

    @staticmethod
    def version_contract(odontogram):
        return {
            "id": odontogram.id_odontogram,
            "visitId": odontogram.visit_id,
            "origin": odontogram.origin,
            "dentition": odontogram.dentition,
            "createdAt": odontogram.created_at,
            "createdById": odontogram.created_by_id,
            "dmft": {
                "decayed": odontogram.dmft_decayed,
                "missing": odontogram.dmft_missing,
                "filled": odontogram.dmft_filled,
                "index": odontogram.dmft_index,
            },
        }
