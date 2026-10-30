"""
P-03: opciones de turno y consultorio (validaciones S0 a S6). Solo lee.
"""

from datetime import timedelta

from django.utils import timezone

from apps.medicos.models import RelMedicoConsultorio
from apps.recepcion.services.adscripcion_evaluacion import sugerir_consultorios
from apps.recepcion.tests._adscripcion_base import AdscripcionTestBase


class SugerenciaConsultoriosTests(AdscripcionTestBase):
    def setUp(self):
        super().setUp()
        self.paciente = self._paciente(no_exp="EXP-NUEVO")

    def _ids(self, opciones):
        return [o.consultorio_id for o in opciones]

    def test_solo_consultorios_familiares_activos_del_centro_con_medico(self):
        valido = self._consultorio(self.clinica5, 1)
        self._consultorio(self.clinica7, 2)
        self._consultorio(self.clinica5, 3, familiar=False)
        self._consultorio(self.clinica5, 4, con_medico=False)
        inactivo = self._consultorio(self.clinica5, 5)
        inactivo.is_active = False
        inactivo.save()
        self.assertEqual(self._ids(sugerir_consultorios(self.paciente, self.clinica5.id)), [valido.id])

    def test_excluye_consultorio_con_medico_que_ya_termino(self):
        consultorio = self._consultorio(self.clinica5, 1)
        RelMedicoConsultorio.objects.filter(consultorio=consultorio).update(
            fecha_fin=timezone.localdate() - timedelta(days=1),
        )
        self.assertEqual(sugerir_consultorios(self.paciente, self.clinica5.id), [])

    def test_ordena_por_carga_y_numero_y_marca_la_primera(self):
        cargado = self._consultorio(self.clinica5, 1)
        libre_b = self._consultorio(self.clinica5, 3)
        libre_a = self._consultorio(self.clinica5, 2)
        self._adscribir(self._paciente(no_exp="EXP-OTRO"), cargado)
        opciones = sugerir_consultorios(self.paciente, self.clinica5.id)
        self.assertEqual(self._ids(opciones), [libre_a.id, libre_b.id, cargado.id])
        self.assertEqual([o.carga for o in opciones], [0, 0, 1])
        self.assertEqual([o.sugerida for o in opciones], [True, False, False])

    def test_excluye_consultorios_llenos(self):
        lleno = self._consultorio(self.clinica5, 1, capacidad=1)
        con_lugar = self._consultorio(self.clinica5, 2, capacidad=2)
        self._adscribir(self._paciente(no_exp="EXP-OTRO"), lleno)
        self.assertEqual(self._ids(sugerir_consultorios(self.paciente, self.clinica5.id)), [con_lugar.id])

    def test_filtra_por_turno(self):
        self._consultorio(self.clinica5, 1, self.matutino)
        vespertino = self._consultorio(self.clinica5, 2, self.vespertino)
        opciones = sugerir_consultorios(self.paciente, self.clinica5.id, turno_id=self.vespertino.id)
        self.assertEqual(self._ids(opciones), [vespertino.id])
        self.assertEqual(opciones[0].turno, "Vespertino")

    def test_no_cuenta_recien_nacidos_ya_vinculados(self):
        consultorio = self._consultorio(self.clinica5, 1, capacidad=1)
        self._adscribir(self._recien_nacido(no_exp="EXP-OTRO", vinculado=True), consultorio)
        opciones = sugerir_consultorios(self.paciente, self.clinica5.id)
        self.assertEqual(self._ids(opciones), [consultorio.id])
        self.assertEqual(opciones[0].carga, 0)

    def test_sin_opciones(self):
        self.assertEqual(sugerir_consultorios(self.paciente, self.clinica5.id), [])


class SugerenciaFamiliaTests(AdscripcionTestBase):
    """S0: si alguien de la familia ya está adscrito en el centro, va primero."""

    def setUp(self):
        super().setUp()
        self.libre = self._consultorio(self.clinica5, 1)
        self.de_la_familia = self._consultorio(self.clinica5, 2)
        self.titular = self._paciente(no_exp="EXP-FAM", pk_num=0)
        self._adscribir(self.titular, self.de_la_familia)

    def test_sugiere_primero_el_consultorio_de_la_familia_aunque_tenga_mas_carga(self):
        conyuge = self._paciente(no_exp="EXP-FAM", pk_num=1)
        opciones = sugerir_consultorios(conyuge, self.clinica5.id)
        self.assertEqual(opciones[0].consultorio_id, self.de_la_familia.id)
        self.assertTrue(opciones[0].es_de_la_familia)
        self.assertTrue(opciones[0].sugerida)
        self.assertFalse(opciones[1].es_de_la_familia)

    def test_recien_nacido_tambien_va_con_su_familia(self):
        bebe = self._recien_nacido(no_exp="EXP-FAM")
        self.assertEqual(sugerir_consultorios(bebe, self.clinica5.id)[0].consultorio_id, self.de_la_familia.id)

    def test_la_familia_en_otro_centro_no_cuenta(self):
        otro = self._consultorio(self.clinica7, 1)
        hijo = self._paciente(no_exp="EXP-FAM", pk_num=2)
        opciones = sugerir_consultorios(hijo, self.clinica7.id)
        self.assertEqual([o.consultorio_id for o in opciones], [otro.id])
        self.assertFalse(opciones[0].es_de_la_familia)

    def test_familia_llena_no_se_sugiere(self):
        lleno = self._consultorio(self.clinica5, 3, capacidad=1)
        hermano = self._paciente(no_exp="EXP-FAM2", pk_num=0)
        self._adscribir(hermano, lleno)
        hija = self._paciente(no_exp="EXP-FAM2", pk_num=1)
        self.assertNotIn(lleno.id, [o.consultorio_id for o in sugerir_consultorios(hija, self.clinica5.id)])
