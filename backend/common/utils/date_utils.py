"""
Date Utilities
Centralizes date filtering logic.
"""
from datetime import date, timedelta
import calendar

def get_filter_date_range(date_filter, year, month, start_date_str, end_date_str):
    start_date = None
    end_date = None
    
    today = date.today()
    
    if date_filter == "today":
        start_date = today.isoformat()
        end_date = today.isoformat()
    elif date_filter == "this_week":
        start_date = (today - timedelta(days=today.weekday())).isoformat()
        end_date = today.isoformat()
    elif date_filter == "this_month":
        start_date = today.replace(day=1).isoformat()
        end_date = today.isoformat()
    elif date_filter == "last_6_months":
        start_date = (today - timedelta(days=180)).isoformat()
        end_date = today.isoformat()
    elif date_filter == "custom":
        if start_date_str:
            start_date = start_date_str
        if end_date_str:
            end_date = end_date_str
            
    if year and year != "all":
        y = int(year)
        if month and month != "all":
            m = int(month)
            _, last_day = calendar.monthrange(y, m)
            start_date = date(y, m, 1).isoformat()
            end_date = date(y, m, last_day).isoformat()
        else:
            start_date = date(y, 1, 1).isoformat()
            end_date = date(y, 12, 31).isoformat()
    elif month and month != "all":
        y = today.year
        m = int(month)
        _, last_day = calendar.monthrange(y, m)
        start_date = date(y, m, 1).isoformat()
        end_date = date(y, m, last_day).isoformat()
        
    return start_date, end_date
