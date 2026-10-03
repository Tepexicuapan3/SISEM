from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase

from apps.consulta_medica.models import ChangeLog
from apps.consulta_medica.services.change_log_service import (
    PROCESS_SERMED_SYNC,
    build_key,
    changed_values,
    record_change,
    snapshot,
)


class ChangeLogServiceTests(TestCase):
    def _record(self, **overrides):
        data = {
            "table": "cns_paciente",
            "key": build_key("id_paciente", 15),
            "action": ChangeLog.Action.UPDATE,
            "reason": ChangeLog.Reason.SERMED_SYNC,
            "user": PROCESS_SERMED_SYNC,
        }
        data.update(overrides)
        return record_change(**data)

    def test_modificacion_guarda_solo_las_columnas_que_cambiaron(self):
        entry = self._record(
            previous={"ds_nombre": "JUAN", "ds_paterno": "PEREZ", "fe_nacimiento": date(1980, 1, 2)},
            new={"ds_nombre": "JUAN CARLOS", "ds_paterno": "PEREZ", "fe_nacimiento": date(1980, 1, 2)},
        )

        entry.refresh_from_db()
        self.assertEqual(entry.previous_value, {"ds_nombre": "JUAN"})
        self.assertEqual(entry.new_value, {"ds_nombre": "JUAN CARLOS"})
        self.assertEqual(entry.reason, "SINCRONIZACION SERMED")
        self.assertEqual(entry.user, "SYNC_SERMED")

    def test_modificacion_sin_cambios_no_escribe(self):
        entry = self._record(previous={"ds_nombre": "JUAN"}, new={"ds_nombre": "JUAN"})

        self.assertIsNone(entry)
        self.assertFalse(ChangeLog.objects.exists())

    def test_alta_no_guarda_valor_anterior(self):
        entry = self._record(
            table="cns_identificador_paciente",
            key=build_key("PK_NUM", 88731),
            action=ChangeLog.Action.CREATE,
            previous={"ignorado": 1},
            new={"id_paciente": 15},
        )

        self.assertIsNone(entry.previous_value)
        self.assertEqual(entry.new_value, {"id_paciente": 15})
        self.assertEqual(entry.key, "PK_NUM|88731")

    def test_baja_no_guarda_valor_nuevo(self):
        entry = self._record(
            action=ChangeLog.Action.DELETE,
            reason=ChangeLog.Reason.MERGE,
            previous={"sw_status": "A"},
            new={"sw_status": "B"},
        )

        self.assertEqual(entry.previous_value, {"sw_status": "A"})
        self.assertIsNone(entry.new_value)

    def test_serializa_fechas_y_decimales(self):
        entry = self._record(
            previous={"fe_nacimiento": date(1980, 1, 2), "peso": Decimal("70.50")},
            new={"fe_nacimiento": date(1981, 1, 2), "peso": Decimal("71.00")},
        )

        entry.refresh_from_db()
        self.assertEqual(entry.new_value, {"fe_nacimiento": "1981-01-02", "peso": "71.00"})

    def test_acepta_usuario_como_objeto_o_id(self):
        por_objeto = self._record(user=SimpleNamespace(pk=42), previous={"a": 1}, new={"a": 2})
        por_id = self._record(user=42, previous={"a": 1}, new={"a": 3})

        self.assertEqual(por_objeto.user, "42")
        self.assertEqual(por_id.user, "42")

    def test_rechaza_cambio_sin_motivo_usuario_o_accion_valida(self):
        with self.assertRaises(ValueError):
            self._record(reason="  ", previous={"a": 1}, new={"a": 2})
        with self.assertRaises(ValueError):
            self._record(user=None, previous={"a": 1}, new={"a": 2})
        with self.assertRaises(ValueError):
            self._record(action="X", previous={"a": 1}, new={"a": 2})
        self.assertFalse(ChangeLog.objects.exists())


class ChangeLogHelpersTests(TestCase):
    def test_changed_values_incluye_columnas_nuevas_y_quitadas(self):
        anterior, nuevo = changed_values({"a": 1, "b": 2}, {"b": 2, "c": 3})

        self.assertEqual(anterior, {"a": 1, "c": None})
        self.assertEqual(nuevo, {"a": None, "c": 3})

    def test_snapshot_lee_los_campos_pedidos(self):
        instancia = SimpleNamespace(ds_nombre="ANA", curp=None, otro="x")

        self.assertEqual(snapshot(instancia, ["ds_nombre", "curp"]), {"ds_nombre": "ANA", "curp": None})

    def test_build_key_une_componentes(self):
        self.assertEqual(build_key("CD_FAMILIAR", 52895), "CD_FAMILIAR|52895")
        with self.assertRaises(ValueError):
            build_key()
