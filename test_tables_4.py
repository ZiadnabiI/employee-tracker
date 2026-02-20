from database import SessionLocal, Company, Supervisor, Employee, EmployeeLog, AppLog, Screenshot, Department, AuthToken

session = SessionLocal()
models = [Company, Supervisor, Employee, EmployeeLog, AppLog, Screenshot, Department, AuthToken]

with open('db_errors.txt', 'w', encoding='utf-8') as f:
    for m in models:
        try:
            session.query(m).first()
            f.write(f"{m.__name__}: OK\n")
        except Exception as e:
            f.write(f"{m.__name__} ERROR: {getattr(e, 'orig', e)}\n")
