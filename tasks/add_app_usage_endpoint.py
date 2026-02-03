@app.get("/api/app-usage-stats")
async def get_app_usage_stats(request: Request, employee_name: Optional[str] = None, db: Session = Depends(get_db)):
    """Get top apps usage stats - can be filtered by employee"""
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    query = db.query(AppLog).filter(AppLog.timestamp >= today_start)
    
    # Filter by company employees
    company_id = token_data["company_id"]
    is_super_admin = token_data.get("is_super_admin", False)
    
    if not is_super_admin:
        # Get company employees first
        employees = db.query(Employee).filter(Employee.company_id == company_id).all()
        emp_names = [e.name for e in employees]
        query = query.filter(AppLog.employee_name.in_(emp_names))
    
    # Filter by specific employee if requested
    if employee_name:
        query = query.filter(AppLog.employee_name == employee_name)
        
    logs = query.all()
    
    # Aggregate duration by app
    app_durations = {}
    
    for log in logs:
        app_name = log.app_name
        duration = log.duration_seconds
        app_durations[app_name] = app_durations.get(app_name, 0) + duration
        
    # Sort by duration
    sorted_apps = sorted(app_durations.items(), key=lambda x: x[1], reverse=True)
    
    # Format for chart (Top 10)
    top_apps = [{"app": name, "duration": dur} for name, dur in sorted_apps[:10]]
    
    return {"top_apps": top_apps}
