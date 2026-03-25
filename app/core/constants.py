"""
Константы для справочных таблиц БД.
Значения соответствуют записям, вставленным в init.sql.
"""


class RightCategory:
    AUTHOR = 1   # Авторские права
    RELATED = 2  # Смежные права


class RightUsageType:
    ALL = 1   # All rights
    PUB = 2   # Public
    MOB = 3   # Mobile
    INT = 4   # Internet


class FindingSource:
    ISRC = 1
    LABEL_OWN_CODE = 2
    NAME = 3
    NAME_ARTIST = 4
    NAME_AUTHOR = 5
