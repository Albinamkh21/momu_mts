import csv
import os
import xlsxwriter

class BaseCSVWriter:
    def __init__(self, path, headers):
        self.file = open(path, mode='w', encoding='utf-8-sig', newline='')
        self.writer = csv.writer(self.file, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        self.writer.writerow(headers)
    
    def write_rows(self, rows):
        self.writer.writerows(rows)
        
    def close(self):
        self.file.close()

    

class BaseExcelWriter:
    def __init__(self, path, headers):
        # constant_memory экономит ОЗУ на больших файлах
        self.workbook = xlsxwriter.Workbook(path, {'constant_memory': True})
        self.worksheet = self.workbook.add_worksheet("Каталог")

        self._format_cache = {}

        # Стиль для цветной шапки
        self.header_format = self.workbook.add_format({
            'bold': True, 'font_name': 'Calibri', 'font_size': 11,
            'bg_color': '#D3D3D3', 'border': 1, 'align': 'center'
        })
        self.cell_format = self.workbook.add_format({'font_name': 'Calibri', 'font_size': 11})
        self.max_lens = [len(str(h)) for h in headers]
        
        # Пишем шапку
        for col_idx, header in enumerate(headers):
            self.worksheet.write(0, col_idx, header, self.header_format)
        self.current_row = 1

    def _get_format(self, **kwargs):
        """Создает или возвращает уже имеющийся формат из кеша."""
        key = tuple(sorted(kwargs.items()))
        if key not in self._format_cache:
            self._format_cache[key] = self.workbook.add_format(dict(kwargs))
        return self._format_cache[key]
    
    def write_formatted_row(
        self, 
        row: list, 
        row_bg_color: str = None, 
        text_colors: dict = None, 
        bold_cols: set = None
    ):
        self.worksheet.set_row(self.current_row, 20)
        text_colors = text_colors or {}
        bold_cols = bold_cols or set()

        for col_idx, val in enumerate(row):
            cell_val = "" if val is None else val

            # Авто-конвертация строк в числа (чтобы "доли прав" выравнивались правильно)
            if isinstance(cell_val, str):
                # Игнорируем штрихкоды, начинающиеся с нуля (например, '01234')
                if not (cell_val.startswith('0') and not cell_val.startswith('0.') and len(cell_val) > 1):
                    try:
                        if '.' in cell_val or ',' in cell_val:
                            cell_val = float(cell_val.replace(',', '.'))
                        else:
                            cell_val = int(cell_val)
                    except ValueError:
                        pass

            text_color = text_colors.get(col_idx)
            is_bold = col_idx in bold_cols

            fmt_kwargs = {
                'font_name': 'Calibri',
                'font_size': 11,
                'valign': 'vcenter',
                'border': 1,
            }
            if row_bg_color:
                fmt_kwargs['bg_color'] = row_bg_color
            if is_bold:
                fmt_kwargs['bold'] = True
            if text_color:
                fmt_kwargs['font_color'] = text_color  # Задаем цвет текста вместо заливки

            cell_fmt = self._get_format(**fmt_kwargs)
            self.worksheet.write(self.current_row, col_idx, cell_val, cell_fmt)

            val_str_len = len(str(cell_val))
            if col_idx < len(self.max_lens) and val_str_len > self.max_lens[col_idx]:
                self.max_lens[col_idx] = val_str_len

        self.current_row += 1

    def write_rows(self, rows):
        for row in rows:
            for col_idx, item in enumerate(row):
                val = "" if item is None else item
                self.worksheet.write(self.current_row, col_idx, val, self.cell_format)
                
                # Копим длину для автоширины колонок
                val_str_len = len(str(val))
                if val_str_len > self.max_lens[col_idx]:
                    self.max_lens[col_idx] = val_str_len
            self.current_row += 1
        
    def close(self):
        # Выставляем ширину колонок по максимальной длине (но не более 50)
        for col_idx, max_len in enumerate(self.max_lens):
            self.worksheet.set_column(col_idx, col_idx, min(max_len + 3, 50))
        self.workbook.close()    

class TomeCSVWriter:
    def __init__(self, base_filename, storage_dir, headers, max_rows=500000):
        self.base_filename = base_filename
        self.storage_dir = storage_dir
        self.headers = headers
        self.max_rows = max_rows
        self.tome_index = 1
        self.rows_in_tome = 0
        self.tome_paths = []
        self.current_writer = None
        self._open_new_tome()

    def _open_new_tome(self):
        if self.current_writer:
            self.current_writer.close()
        path = os.path.join(self.storage_dir, f"{self.base_filename}_tom_{self.tome_index}.csv")
        self.tome_paths.append(path)
        self.current_writer = BaseCSVWriter(path, self.headers)
        self.tome_index += 1
        self.rows_in_tome = 0

    def write_rows(self, rows):
        for row in rows:
            if self.rows_in_tome >= self.max_rows:
                self._open_new_tome()
            self.current_writer.writer.writerow(row)
            self.rows_in_tome += 1

    def close(self):
        if self.current_writer:
            self.current_writer.close()
class TomeExcelWriter:
    def __init__(self, base_filename, storage_dir, headers, max_rows=500000):
        self.base_filename = base_filename
        self.storage_dir = storage_dir
        self.headers = headers
        self.max_rows = max_rows
        self.tome_index = 1
        self.rows_in_tome = 0
        self.tome_paths = []
        self.current_writer = None
        self._open_new_tome()

    def _open_new_tome(self):
        if self.current_writer:
            self.current_writer.close()
        path = os.path.join(self.storage_dir, f"{self.base_filename}_tom_{self.tome_index}.xlsx")
        self.tome_paths.append(path)
        self.current_writer = BaseExcelWriter(path, self.headers)
        self.tome_index += 1
        self.rows_in_tome = 0

    def write_rows(self, rows):
        chunk_buffer = []
        for row in rows:
            # Если текущий том переполнился, сбрасываем накопленный буфер и открываем новый том
            if self.rows_in_tome >= self.max_rows:
                if chunk_buffer:
                    self.current_writer.write_rows(chunk_buffer)
                    chunk_buffer = []
                self._open_new_tome()
            
            chunk_buffer.append(row)
            self.rows_in_tome += 1
            
        # Дозаписываем остатки строк в текущий работающий том
        if chunk_buffer:
            self.current_writer.write_rows(chunk_buffer)

    def close(self):
        if self.current_writer:
            self.current_writer.close()

class TomeWriterFactory:
    @staticmethod
    def create(writer_type: str, base_filename: str, storage_dir: str, headers: list, max_rows: int = 500000):
        if writer_type == "xlsx":
            return TomeExcelWriter(base_filename, storage_dir, headers, max_rows)
        elif writer_type == "csv":
            return TomeCSVWriter(base_filename, storage_dir, headers, max_rows)
        else:
            raise ValueError(f"Неизвестный тип райтера: {writer_type}")            