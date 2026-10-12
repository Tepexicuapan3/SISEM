# Los perfiles por tipo de personal (DetUsuarioMedico / DetUsuarioEnfermeria /
# DetUsuarioAdministrativo) se eliminaron en la migración 0003: duplicaban las
# cédulas (det_usuario_cedulas), la especialidad (catálogo de médicos) y el área
# clínica (det_usuarios) y ningún módulo los consumía.
