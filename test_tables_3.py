from database import SessionLocal, Company, Supervisor, Employee, EmployeeLog, AppLog, Screenshot, Department, AuthToken

session = SessionLocal()
models = [Company, Supervisor, Employee, EmployeeLog, AppLog, Screenshot, Department, AuthToken]

for m in models:
    try:
        session.query(m).first()
        print(f"{m.__name__}: OK")
    except Exception as e:
        print(f"{m.__name__} ERROR: {getattr(e, 'orig', e)}")
