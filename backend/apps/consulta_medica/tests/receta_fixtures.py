"""Datos compartidos por los tests de receta.

Via, frecuencia y duracion son obligatorias en cada medicamento nuevo
(``add_prescription_item``, RIS art. 30). Los tests que no prueban esa regla
las pasan con este valor. Las claves sirven igual para el caso de uso
(kwargs) y para el payload de la API.
"""

ADMINISTRATION = {"route": "oral", "frequency": "Cada 8 horas", "duration": "5 dias"}
