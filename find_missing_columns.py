from sqlalchemy import inspect
from database import engine, Base

inspector = inspect(engine)
tables = Base.metadata.tables

with open('all_missing_columns.txt', 'w', encoding='utf-8') as f:
    for table_name in tables.keys():
        if not inspector.has_table(table_name):
            f.write(f"Table '{table_name}' MISSING ENTIRELY!\n")
            continue
            
        db_columns = [col['name'] for col in inspector.get_columns(table_name)]
        model_columns = tables[table_name].columns.keys()
        missing = set(model_columns) - set(db_columns)
        if missing:
            f.write(f"Table '{table_name}' missing columns: {', '.join(missing)}\n")
        else:
            f.write(f"Table '{table_name}': OK\n")
