"""
Migra las alergias en texto libre YA EXISTENTES en SISEM
(``ClinicalHistory.allergies`` y los 6 campos ``StomatologyHistory.allergy_*``)
al modelo estructurado ``Allergy`` (change `alergias-unificadas`).

A diferencia de los comandos ``migrar_*_legacy.py`` (que leen de MySQL), esto
es una migracion de datos DENTRO de SISEM (Postgres -> Postgres): unifica dos
fuentes de texto libre duplicadas que ya conviven en la misma base, sin tocar
ningun sistema externo.

No intenta separar automaticamente listas como "penicilina, mariscos" en
alergias individuales -- eso requiere criterio clinico que este comando no
tiene. Cada campo no vacio se convierte en UNA fila de Allergy con el texto
completo (truncado a 255 caracteres como `substance`, el resto se preserva
en `reaction` si excede eso). La severidad se importa como MODERATE por
defecto porque no se puede inferir de forma confiable de texto libre --
queda reportado al final para que el area medica la revise/corrija con el
nuevo endpoint estructurado (`PATCH patients/<no_exp>/allergies/<id>`).

Idempotente: si ya existe una Allergy con el mismo (no_exp, pk_num, source,
substance), no se crea una duplicada -- permite correr el comando mas de una
vez sin acumular filas repetidas.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import DatabaseError, transaction

from apps.consulta_medica.models import Allergy, ClinicalHistory, StomatologyHistory

_STOMATOLOGY_FIELD_TO_CATEGORY = {
    "allergy_medications": Allergy.Category.MEDICATION,
    "allergy_dental_material": Allergy.Category.DENTAL_MATERIAL,
    "allergy_anesthesia": Allergy.Category.ANESTHESIA,
    "allergy_food": Allergy.Category.FOOD,
    "allergy_environment": Allergy.Category.ENVIRONMENTAL,
    "allergy_other": Allergy.Category.OTHER,
}

_SUBSTANCE_MAX_LENGTH = 255


def _split_substance_and_reaction(raw_text):
    text = raw_text.strip()
    if len(text) <= _SUBSTANCE_MAX_LENGTH:
        return text, None
    return text[:_SUBSTANCE_MAX_LENGTH], text


class Command(BaseCommand):
    help = (
        "Migra ClinicalHistory.allergies y StomatologyHistory.allergy_* "
        "(texto libre) a filas estructuradas de Allergy. Ver docstring del "
        "modulo para el criterio de conversion. Idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="No escribe nada, solo reporta cuantas filas se crearian.",
        )
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Limita cuantos registros de historia procesar (para pruebas).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        errores = []

        creados_generales = self._migrate_clinical_history(
            dry_run=dry_run, limit=limit, errores=errores,
        )
        creados_dentales = self._migrate_stomatology_history(
            dry_run=dry_run, limit=limit, errores=errores,
        )

        prefix = "[DRY-RUN] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Alergias creadas -- Medicina General: {creados_generales}, "
            f"Estomatologia: {creados_dentales}, Errores: {len(errores)}"
        ))
        for no_exp, pk_num, detail in errores:
            self.stdout.write(self.style.WARNING(f"  {no_exp}/{pk_num}: {detail}"))

        if creados_generales or creados_dentales:
            self.stdout.write(self.style.WARNING(
                "Revision manual pendiente: el texto migrado puede combinar "
                "varias sustancias en una sola fila (ej. \"penicilina, "
                "mariscos\") -- el area medica debe separarlas con el "
                "endpoint estructurado cuando corresponda. Severidad "
                "importada como 'moderate' por defecto (no se puede inferir "
                "de forma confiable de texto libre)."
            ))

    def _already_migrated(self, *, no_exp, pk_num, source, substance):
        return Allergy.objects.filter(
            no_exp=no_exp, pk_num=pk_num, source=source, substance=substance,
        ).exists()

    def _migrate_clinical_history(self, *, dry_run, limit, errores):
        queryset = (
            ClinicalHistory.objects.exclude(allergies__isnull=True)
            .exclude(allergies__exact="")
            .order_by("id_clinical_history")
        )
        if limit:
            queryset = queryset[:limit]

        count = 0
        for history in queryset:
            substance, reaction = _split_substance_and_reaction(history.allergies)
            if not substance:
                continue
            if self._already_migrated(
                no_exp=history.no_exp, pk_num=history.pk_num,
                source=Allergy.Source.GENERAL, substance=substance,
            ):
                continue

            count += 1
            if dry_run:
                continue
            try:
                with transaction.atomic():
                    Allergy.objects.create(
                        no_exp=history.no_exp,
                        pk_num=history.pk_num,
                        category=Allergy.Category.MEDICATION,
                        substance=substance,
                        severity=Allergy.Severity.MODERATE,
                        reaction=reaction,
                        source=Allergy.Source.GENERAL,
                        created_by_id=None,
                    )
            except DatabaseError as exc:
                errores.append((history.no_exp, history.pk_num, str(exc)))
        return count

    def _migrate_stomatology_history(self, *, dry_run, limit, errores):
        queryset = StomatologyHistory.objects.order_by("id_stomatology_history")
        if limit:
            queryset = queryset[:limit]

        count = 0
        for history in queryset:
            for field_name, category in _STOMATOLOGY_FIELD_TO_CATEGORY.items():
                raw_value = getattr(history, field_name)
                if not raw_value or not raw_value.strip():
                    continue

                substance, reaction = _split_substance_and_reaction(raw_value)
                if self._already_migrated(
                    no_exp=history.no_exp, pk_num=history.pk_num,
                    source=Allergy.Source.STOMATOLOGY, substance=substance,
                ):
                    continue

                count += 1
                if dry_run:
                    continue
                try:
                    with transaction.atomic():
                        Allergy.objects.create(
                            no_exp=history.no_exp,
                            pk_num=history.pk_num,
                            category=category,
                            substance=substance,
                            severity=Allergy.Severity.MODERATE,
                            reaction=reaction,
                            source=Allergy.Source.STOMATOLOGY,
                            created_by_id=None,
                        )
                except DatabaseError as exc:
                    errores.append((history.no_exp, history.pk_num, str(exc)))
        return count
