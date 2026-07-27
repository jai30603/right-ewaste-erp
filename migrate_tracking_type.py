import sys
sys.path.insert(0, 'backend')
from database import get_connection

conn = get_connection()
conn.execute("UPDATE material SET tracking_type = 'QUANTITY_ONLY' WHERE tracking_type = 'PIECES_ONLY'")
count = conn.total_changes
conn.commit()
conn.close()
print(f"Renamed {count} material rows from PIECES_ONLY to QUANTITY_ONLY")
