import polars as pl


def clean_null_bytes(df: pl.DataFrame) -> pl.DataFrame:
    # 1. Все колонки в строку для единообразия
    df = df.with_columns([pl.col("*").cast(pl.String)])

    # 2. Список "ядерной" чистки
    return df.with_columns([
        pl.col("*")
        # Удаляем NULL-байты (literal=True + не-raw строка — ищет реальный байт \x00)
        .str.replace_all("\x00", "", literal=True)
        # Удаляем управляющие символы \x01-\x1F, \x7F и неразрывные пробелы \xA0
        .str.replace_all(r"[\x01-\x1F\x7F\xA0]", "")
        # Убираем обычные пробелы по краям
        .str.strip_chars()
        # Если после чистки осталась пустая строка — делаем её NULL (None)
        .replace("", None)
    ])
