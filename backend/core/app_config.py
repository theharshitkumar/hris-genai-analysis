import os


class Configs:
    BASE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')
    ORIGINAL_DB_PATH = os.path.join(BASE_PATH, 'data', 'sql', 'original_db.db')
    DB_PATH = os.path.join(BASE_PATH, 'data', 'sql', 'custom_db.db')
    CSV_PATH = os.path.join(BASE_PATH, 'data', 'csv', 'employee_data_15000.csv')


configs = Configs()
