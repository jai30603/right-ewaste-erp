import sqlite3
import re
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[4] / "database" / "erp.db"

# List 1: E-Waste Materials
EWASTE_ITEMS = [
    "Air conditioner", "Bike -two wheeler", "CPU", "E waste mixed", "DVD player",
    "Iron box", "Keyboard", "Junction box", "Laptop", "Lcd monitor", "LED TV",
    "Medical Equipment", "Mixy grinder", "Modem", "Mouse", "Mobile Phone",
    "Projector", "Printer/ Scanner", "Power Bank", "Refrigerator", "Speaker",
    "Telephone", "UPS", "Table Fan", "Vacuum cleaner + Water", "Water filter",
    "Washing machine"
]

# List 2: Disposable Items
DISPOSAL_ITEMS = [
    "Battery lead acid water", "Battery lead acid - SMF small", "Battery - Lead acid SMF dry",
    "Battery -Laptop", "Battery dry cell", "Battery - Mobile", "Capacitor & Condensor",
    "Carton box / paper waste", "Display - LCD", "Glass waste", "Membrane filter",
    "Wood / ply wood / palete", "Tonner / Cadridge", "Thermocole /foam", "Waste"
]

# List 3: Scrap Materials
SCRAP_ITEMS = [
    "E-Waste scrap mixed", "Adaptor / Charger", "Aluminium scraps", "Al. Castiron",
    "Aluminium and mild mixed", "Cable mixed", "Choke scraps", "Compressor",
    "Copper scraps", "Electrical item", "Chair office used", "Hard disk",
    "Lighting Equipment", "Lens", "Mild steel", "Mixed material", "Motor -",
    "Plastic scraps", "Plastic abs", "Plastic box", "Radiotor", "Steel",
    "SMPS", "PCB scraps", "Transformer"
]


def generate_material_code(name, existing_codes):
    # Clean non-alphanumeric chars
    clean_name = re.sub(r'[^A-Za-z0-9]', ' ', name).upper()
    tokens = clean_name.split()

    if len(tokens) == 1:
        base_code = f"MAT-{tokens[0][:6]}"
    elif len(tokens) == 2:
        base_code = f"MAT-{tokens[0][:3]}-{tokens[1][:3]}"
    else:
        base_code = f"MAT-{tokens[0][:2]}-{tokens[1][:2]}-{tokens[2][:2]}"

    code = base_code
    seq = 1
    while code in existing_codes:
        code = f"{base_code}-{seq:02d}"
        seq += 1

    existing_codes.add(code)
    return code


def seed_all_master_materials():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get existing materials
    cursor.execute("SELECT material_code, LOWER(material_name) FROM material")
    rows = cursor.fetchall()
    existing_codes = set(r[0] for r in rows)
    existing_names = set(r[1] for r in rows)

    all_items = []
    for item in EWASTE_ITEMS:
        all_items.append((item, "E-Waste"))
    for item in DISPOSAL_ITEMS:
        all_items.append((item, "Disposal"))
    for item in SCRAP_ITEMS:
        all_items.append((item, "Scrap"))

    inserted_count = 0
    skipped_count = 0

    for name, category in all_items:
        norm_name = name.strip().lower()
        if norm_name in existing_names:
            skipped_count += 1
            continue

        code = generate_material_code(name, existing_codes)
        cursor.execute("""
            INSERT INTO material (
                material_code, material_name, category, hsn_code, uom, gst_percentage, tracking_type
            ) VALUES (?, ?, ?, '8549', 'KGS', 18.0, 'BOTH')
        """, (code, name.strip(), category))

        existing_names.add(norm_name)
        inserted_count += 1

    conn.commit()
    conn.close()

    print(f"Master Material Sync Completed!")
    print(f"Total Unique Items Processed: {len(all_items)}")
    print(f"Newly Inserted Master Materials: {inserted_count}")
    print(f"Skipped Duplicates: {skipped_count}")


if __name__ == "__main__":
    seed_all_master_materials()
