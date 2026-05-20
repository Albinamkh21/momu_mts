import csv
import os

class BaseCSVWriter:
    def __init__(self, path, headers):
        self.file = open(path, mode='w', encoding='utf-8-sig', newline='')
        self.writer = csv.writer(self.file, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        self.writer.writerow(headers)
    
    def write_rows(self, rows):
        self.writer.writerows(rows)
        
    def close(self):
        self.file.close()

class TomeWriter:
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