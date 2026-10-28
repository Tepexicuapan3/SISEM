"""Aviso del manager (2026-10-28):
- aut_solicitud.id_paciente pasa a FK a cns_paciente (PROTECT), como en las 22 tablas.
  Se convierte la MISMA columna (RenameField + AlterField); no se crea otra.
- Se quitan tabla_legado / id_legado: el historial del legado no se carga a SIRES.

Depende de consulta_medica 0064 (cns_paciente ya existe ahi), no de 0065/0066:
esas son del plan de identidad y no son requisito de este modulo.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('autorizaciones', '0011_tareas_programadas'),
        ('consulta_medica', '0064_llave_vieja_opcional'),
    ]

    operations = [
        migrations.RemoveConstraint(model_name='solicitud', name='aut_solicitud_resolucion_ck'),
        migrations.RemoveConstraint(model_name='solicitud', name='aut_solicitud_rechazo_motivo_ck'),
        migrations.RemoveConstraint(model_name='solicitud', name='aut_solicitud_legado_uq'),
        migrations.RemoveField(model_name='solicitud', name='tabla_legado'),
        migrations.RemoveField(model_name='solicitud', name='id_legado'),
        migrations.RenameField(model_name='solicitud', old_name='id_paciente', new_name='paciente'),
        migrations.AlterField(
            model_name='solicitud',
            name='paciente',
            field=models.ForeignKey(
                blank=True, db_column='id_paciente', null=True,
                on_delete=django.db.models.deletion.PROTECT, related_name='+', to='consulta_medica.patient',
            ),
        ),
        migrations.AddConstraint(
            model_name='solicitud',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(('estatus__in', ['AUTORIZADA', 'RECHAZADA']), ('fecha_resolucion__isnull', False),
                             ('id_usuario_resolucion__isnull', False)),
                    models.Q(models.Q(('estatus__in', ['AUTORIZADA', 'RECHAZADA']), _negated=True),
                             ('id_usuario_resolucion__isnull', True)),
                    _connector='OR',
                ),
                name='aut_solicitud_resolucion_ck',
            ),
        ),
        migrations.AddConstraint(
            model_name='solicitud',
            constraint=models.CheckConstraint(
                condition=models.Q(models.Q(('estatus', 'RECHAZADA'), _negated=True),
                                   ('motivo_cierre__isnull', False), _connector='OR'),
                name='aut_solicitud_rechazo_motivo_ck',
            ),
        ),
    ]
