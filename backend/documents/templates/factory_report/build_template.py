import os
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

TEMPLATE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = TEMPLATE_DIR / "factory_report_template.xlsx"


def create_factory_report_master_template():
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()

    # Define Fonts
    title_font = Font(name="Calibri", size=14, bold=True, color="000000")
    subtitle_font = Font(name="Calibri", size=11, bold=True, color="000000")
    header_font = Font(name="Calibri", size=10, bold=True, color="000000")
    bold_font = Font(name="Calibri", size=9, bold=True, color="000000")
    regular_font = Font(name="Calibri", size=9, bold=False, color="000000")
    red_font = Font(name="Calibri", size=9, bold=False, color="FF0000")
    bold_red_font = Font(name="Calibri", size=9, bold=True, color="FF0000")

    # Define Fills
    fill_gold = PatternFill(start_color="C4BD97", end_color="C4BD97", fill_type="solid")
    fill_grey = PatternFill(start_color="7F7F7F", end_color="7F7F7F", fill_type="solid")
    fill_cyan = PatternFill(start_color="00FFCC", end_color="00FFCC", fill_type="solid")
    fill_cyan_light = PatternFill(start_color="00FFFF", end_color="00FFFF", fill_type="solid")
    fill_yellow = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    fill_amber = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")
    fill_peach = PatternFill(start_color="FDE9D9", end_color="FDE9D9", fill_type="solid")
    fill_pink = PatternFill(start_color="FFC0CB", end_color="FFC0CB", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="000000"),
        right=Side(style="thin", color="000000"),
        top=Side(style="thin", color="000000"),
        bottom=Side(style="thin", color="000000")
    )

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    # ── 1. EwasteMaterials Sheet ──────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "EwasteMaterials"

    ws1.merge_cells("B1:N1")
    ws1["B1"] = "Right Ewaste Recycle Private Limited,"
    ws1["B1"].font = title_font
    ws1["B1"].alignment = align_center
    ws1["B1"].fill = fill_gold

    ws1.merge_cells("B2:N2")
    ws1["B2"] = "Factory Daily Report"
    ws1["B2"].font = subtitle_font
    ws1["B2"].alignment = align_center
    ws1["B2"].fill = fill_gold

    ws1.merge_cells("A3:D3")
    ws1["A3"] = "Date :31.03.2023"
    ws1["A3"].font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    ws1["A3"].fill = fill_grey
    ws1["A3"].alignment = align_left

    ws1.merge_cells("E3:N3")
    ws1["E3"] = "Branch: Mumbai."
    ws1["E3"].font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    ws1["E3"].fill = fill_grey
    ws1["E3"].alignment = align_right

    # Attendance Box
    ws1["A4"] = "No. of Employees"
    ws1["B4"] = "Worked"
    ws1["C4"] = "On Leave"
    ws1["D4"] = "On Duty"
    for col in ["A", "B", "C", "D"]:
        ws1[f"{col}4"].font = bold_font
        ws1[f"{col}4"].border = thin_border
        ws1[f"{col}4"].alignment = align_center

    ws1["A5"] = "Company Staff"
    ws1["B5"] = 0
    ws1["C5"] = 0
    ws1["D5"] = 0
    ws1["A6"] = "Casual Labourers"
    ws1["B6"] = 0
    ws1["C6"] = 0
    ws1["D6"] = 0
    for r in [5, 6]:
        ws1[f"A{r}"].font = bold_font
        ws1[f"A{r}"].border = thin_border
        for c in ["B", "C", "D"]:
            ws1[f"{c}{r}"].font = bold_red_font if c == "C" else bold_font
            ws1[f"{c}{r}"].border = thin_border
            ws1[f"{c}{r}"].alignment = align_center

    # Main Items Table Header
    headers1 = [
        "S.No", "Particulars", "Opening Stock", "OS (Wt)", "Received Quantity", "Received Weight",
        "Ref. Items (Nos)", "Recycled process", "Recycled (Nos)", "Recycled Quantity", "Closing Stock", "CS(Wt)", "Rate", "Amount"
    ]
    for col_idx, h in enumerate(headers1, 1):
        cell = ws1.cell(row=7, column=col_idx, value=h)
        cell.font = bold_font
        cell.alignment = align_center
        cell.border = thin_border
        cell.fill = fill_peach

    items1 = [
        "Air conditioner", "Bike -two wheeler", "CPU", "E waste mixed", "DVD player", "Iron box",
        "Keyboard", "Junction box", "Laptop", "Lcd monitor", "LED TV", "Medical Equipment",
        "Mixy grinder", "Modem", "Mouse", "Mobile Phone", "Projector", "Printer/ Scanner",
        "Power Bank", "Refrigerator", "Speaker", "Telephone", "UPS", "Table Fan",
        "Vacuum cleaner + Water", "Water filter", "Washing machine"
    ]

    for idx, item in enumerate(items1, 1):
        r = idx + 7
        ws1.cell(row=r, column=1, value=idx).alignment = align_center
        ws1.cell(row=r, column=2, value=item).alignment = align_left
        ws1.cell(row=r, column=3, value=0).alignment = align_right
        ws1.cell(row=r, column=4, value=0.0).number_format = "0.000"
        ws1.cell(row=r, column=11, value=0).alignment = align_right
        ws1.cell(row=r, column=12, value=0.0).number_format = "0.000"
        ws1.cell(row=r, column=13, value=0.0).number_format = "0.00"
        
        amt_cell = ws1.cell(row=r, column=14, value=f"=L{r}*M{r}")
        amt_cell.number_format = "0.000"
        amt_cell.font = red_font
        amt_cell.alignment = align_right

        for c in range(1, 15):
            ws1.cell(row=r, column=c).border = thin_border

    # Total Row (Row 35)
    tot_row = len(items1) + 8
    ws1.cell(row=tot_row, column=2, value="Total").font = bold_font
    ws1.cell(row=tot_row, column=3, value=f"=SUM(C8:C{tot_row-1})").font = bold_font
    ws1.cell(row=tot_row, column=4, value=f"=SUM(D8:D{tot_row-1})").font = bold_font
    ws1.cell(row=tot_row, column=5, value=f"=SUM(E8:E{tot_row-1})").font = bold_font
    ws1.cell(row=tot_row, column=6, value=f"=SUM(F8:F{tot_row-1})").font = bold_font
    ws1.cell(row=tot_row, column=7, value=f"=SUM(G8:G{tot_row-1})").font = bold_font
    ws1.cell(row=tot_row, column=9, value=f"=SUM(I8:I{tot_row-1})").font = bold_font
    ws1.cell(row=tot_row, column=10, value=f"=SUM(J8:J{tot_row-1})").font = bold_font
    ws1.cell(row=tot_row, column=11, value=f"=SUM(K8:K{tot_row-1})").font = bold_font
    ws1.cell(row=tot_row, column=12, value=f"=SUM(L8:L{tot_row-1})").font = bold_font
    ws1.cell(row=tot_row, column=14, value=f"=SUM(N8:N{tot_row-1})").font = bold_red_font

    for c in range(1, 15):
        cell = ws1.cell(row=tot_row, column=c)
        cell.border = thin_border
        cell.fill = fill_amber

    # ── Bottom Summary Tables on EwasteMaterials ─────────────────────────────
    # Table 1: Activities of the Day (Rows 37-41, Cols B to E)
    ws1.merge_cells("B37:E37")
    ws1["B37"] = "Activities of the Day"
    ws1["B37"].font = bold_font
    ws1["B37"].alignment = align_center

    for r in range(37, 42):
        for c in range(2, 6):
            ws1.cell(row=r, column=c).border = thin_border

    # Table 2: Stock Movement for the Day (Rows 42-44, Cols B to F)
    ws1.merge_cells("B42:F42")
    ws1["B42"] = "Stock Movement for the Day"
    ws1["B42"].font = bold_font
    ws1["B42"].alignment = align_center

    headers_sm = ["Opening stock", "Incoming", "Outgoing", "Recycled", "Closing stock"]
    fills_sm = [fill_yellow, fill_cyan_light, fill_pink, fill_amber, fill_yellow]

    for idx, (h_title, f_color) in enumerate(zip(headers_sm, fills_sm), 2):
        cell = ws1.cell(row=43, column=idx, value=h_title)
        cell.font = bold_red_font
        cell.alignment = align_center
        cell.border = thin_border
        cell.fill = f_color

    # Stock Movement Values Row (Row 44)
    ws1.cell(row=44, column=2, value="=D35+Disposal!C22+ScrapMaterials!C32").font = bold_font # Opening Stock
    ws1.cell(row=44, column=3, value="=F35+Disposal!D22+ScrapMaterials!D32").font = bold_font # Incoming
    ws1.cell(row=44, column=4, value="=G35+Disposal!G22+ScrapMaterials!G32").font = bold_font # Outgoing
    ws1.cell(row=44, column=5, value="=J35+Disposal!E22+ScrapMaterials!E32").font = bold_font # Recycled
    ws1.cell(row=44, column=6, value="=L35+Disposal!H22+ScrapMaterials!H32").font = bold_font # Closing Stock

    for c in range(2, 7):
        cell = ws1.cell(row=44, column=c)
        cell.border = thin_border
        cell.alignment = align_center
        cell.number_format = "0.000"

    # Table 3: Closing Stock Position of the Day (Rows 37-43, Cols H to K)
    ws1.merge_cells("H37:J37")
    ws1["H37"] = "Closing Stock Position of the Day"
    ws1["H37"].font = bold_font
    ws1["H37"].alignment = align_center
    ws1["H37"].border = thin_border

    ws1["K37"] = "Total value"
    ws1["K37"].font = bold_font
    ws1["K37"].alignment = align_center
    ws1["K37"].border = thin_border

    cs_rows_def = [
        (1, "E - Waste Materials", "=L35", "=N35"),
        (2, "Scrap Material", "=ScrapMaterials!H32", "=ScrapMaterials!J32"),
        (3, "Disposal material", "=Disposal!H22", "=Disposal!J22")
    ]

    for r_idx, s_no, cat_name, wt_form, val_form in zip(range(38, 41), [1, 2, 3], ["E - Waste Materials", "Scrap Material", "Disposal material"], ["=L35", "=ScrapMaterials!H32", "=Disposal!H22"], ["=N35", "=ScrapMaterials!J32", "=Disposal!J22"]):
        ws1.cell(row=r_idx, column=8, value=s_no).alignment = align_center
        ws1.cell(row=r_idx, column=8).border = thin_border

        ws1.cell(row=r_idx, column=9, value=cat_name).font = regular_font
        ws1.cell(row=r_idx, column=9).fill = fill_peach
        ws1.cell(row=r_idx, column=9).border = thin_border

        cell_wt = ws1.cell(row=r_idx, column=10, value=wt_form)
        cell_wt.font = bold_font
        cell_wt.alignment = align_right
        cell_wt.number_format = "0.000"
        cell_wt.border = thin_border

        cell_val = ws1.cell(row=r_idx, column=11, value=val_form)
        cell_val.font = bold_font
        cell_val.alignment = align_right
        cell_val.number_format = "0.000"
        cell_val.fill = fill_yellow
        cell_val.border = thin_border

    # Empty Row 41
    for c in range(8, 12):
        ws1.cell(row=41, column=c).border = thin_border

    # Total Row 42 for Closing Stock Position
    ws1.merge_cells("H42:I42")
    ws1["H42"] = "Total (Kgs)"
    ws1["H42"].font = bold_red_font
    ws1["H42"].alignment = align_center
    ws1["H42"].fill = fill_yellow
    ws1["H42"].border = thin_border
    ws1["I42"].border = thin_border

    ws1.cell(row=42, column=10, value="=SUM(J38:J40)").font = bold_red_font
    ws1.cell(row=42, column=10).fill = fill_yellow
    ws1.cell(row=42, column=10).alignment = align_right
    ws1.cell(row=42, column=10).number_format = "0.000"
    ws1.cell(row=42, column=10).border = thin_border

    ws1.cell(row=42, column=11, value="=SUM(K38:K40)").font = bold_red_font
    ws1.cell(row=42, column=11).fill = fill_yellow
    ws1.cell(row=42, column=11).alignment = align_right
    ws1.cell(row=42, column=11).number_format = "0.000"
    ws1.cell(row=42, column=11).border = thin_border

    # ── 2. Disposal Sheet ─────────────────────────────────────────────────────
    ws2 = wb.create_sheet(title="Disposal")
    ws2.merge_cells("A1:J1")
    ws2["A1"] = "Right Ewaste Recycle Private Limited,"
    ws2["A1"].font = title_font
    ws2["A1"].alignment = align_center
    ws2["A1"].fill = fill_gold

    ws2.merge_cells("A2:J2")
    ws2["A2"] = "Factory Daily Report"
    ws2["A2"].font = subtitle_font
    ws2["A2"].alignment = align_center
    ws2["A2"].fill = fill_gold

    ws2.merge_cells("A3:C3")
    ws2["A3"] = "Date :31.03.2023"
    ws2["A3"].font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    ws2["A3"].fill = fill_grey

    ws2.merge_cells("D3:J3")
    ws2["D3"] = "Branch: Mumbai."
    ws2["D3"].font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    ws2["D3"].alignment = align_right
    ws2["D3"].fill = fill_grey

    ws2.merge_cells("A5:J5")
    ws2["A5"] = "E Waste Materials- Disposable Items"
    ws2["A5"].font = bold_font
    ws2["A5"].alignment = align_center
    ws2["A5"].fill = fill_cyan

    headers2 = ["S.No", "Particulars", "OS(Wt) (Kgs)", "Quantity Received (Kgs)", "Recycled (Wt)", "Recycled Qty of Scrap (Kgs)", "Disposed (Wt)", "CS (Wt) (Kgs)", "Rate", "Amount"]
    for col_idx, h in enumerate(headers2, 1):
        cell = ws2.cell(row=6, column=col_idx, value=h)
        cell.font = bold_font
        cell.alignment = align_center
        cell.border = thin_border
        cell.fill = fill_peach

    items2 = [
        "Battery lead acid water", "Battery lead acid - SMF small", "Battery - Lead acid SMF dry",
        "Battery -Laptop", "Battery dry cell", "Battery - Mobile", "Capacitor & Condensor",
        "Carton box / paper waste", "Display - LCD", "Glass waste", "Membrane filter",
        "Wood / ply wood / palete", "Tonner / Cadridge", "Thermocole /foam", "Waste"
    ]
    for idx, item in enumerate(items2, 1):
        r = idx + 6
        ws2.cell(row=r, column=1, value=idx).alignment = align_center
        ws2.cell(row=r, column=2, value=item).alignment = align_left
        ws2.cell(row=r, column=3, value=0.0).number_format = "0.000"
        ws2.cell(row=r, column=8, value=0.0).number_format = "0.000"
        ws2.cell(row=r, column=9, value=0.0).number_format = "0.00"
        amt_cell = ws2.cell(row=r, column=10, value=f"=H{r}*I{r}")
        amt_cell.number_format = "0.000"
        amt_cell.font = red_font

        for c in range(1, 11):
            ws2.cell(row=r, column=c).border = thin_border

    tot_row2 = len(items2) + 7
    ws2.cell(row=tot_row2, column=2, value="Total").font = bold_font
    ws2.cell(row=tot_row2, column=3, value=f"=SUM(C7:C{tot_row2-1})").font = bold_font
    ws2.cell(row=tot_row2, column=4, value=f"=SUM(D7:D{tot_row2-1})").font = bold_font
    ws2.cell(row=tot_row2, column=5, value=f"=SUM(E7:E{tot_row2-1})").font = bold_font
    ws2.cell(row=tot_row2, column=6, value=f"=SUM(F7:F{tot_row2-1})").font = bold_font
    ws2.cell(row=tot_row2, column=7, value=f"=SUM(G7:G{tot_row2-1})").font = bold_font
    ws2.cell(row=tot_row2, column=8, value=f"=SUM(H7:H{tot_row2-1})").font = bold_font
    ws2.cell(row=tot_row2, column=10, value=f"=SUM(J7:J{tot_row2-1})").font = bold_red_font
    for c in range(1, 11):
        cell = ws2.cell(row=tot_row2, column=c)
        cell.border = thin_border
        cell.fill = fill_amber

    # ── 3. ScrapMaterials Sheet ───────────────────────────────────────────────
    ws3 = wb.create_sheet(title="ScrapMaterials")
    ws3.merge_cells("A1:J1")
    ws3["A1"] = "Right Ewaste Recycle Private Limited,"
    ws3["A1"].font = title_font
    ws3["A1"].alignment = align_center
    ws3["A1"].fill = fill_gold

    ws3.merge_cells("A2:J2")
    ws3["A2"] = "Factory Daily Report"
    ws3["A2"].font = subtitle_font
    ws3["A2"].alignment = align_center
    ws3["A2"].fill = fill_gold

    ws3.merge_cells("A3:C3")
    ws3["A3"] = "Date :31.03.2023"
    ws3["A3"].font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    ws3["A3"].fill = fill_grey

    ws3.merge_cells("D3:J3")
    ws3["D3"] = "Branch: Mumbai."
    ws3["D3"].font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    ws3["D3"].alignment = align_right
    ws3["D3"].fill = fill_grey

    ws3.merge_cells("A5:J5")
    ws3["A5"] = "Waste Material Scrap - Stock, Refurbished and Recycled Material Details"
    ws3["A5"].font = bold_font
    ws3["A5"].alignment = align_center
    ws3["A5"].fill = fill_cyan

    headers3 = ["S.No", "Name of the Material", "Opening Stock (Kgs)", "Quantity Received", "Recycled Quantity (Kgs)", "Recycled Qty of (Kgs)", "Sold Quantity (Kgs)", "Closing Stock (Kgs)", "Rate", "Amount"]
    for col_idx, h in enumerate(headers3, 1):
        cell = ws3.cell(row=6, column=col_idx, value=h)
        cell.font = bold_font
        cell.alignment = align_center
        cell.border = thin_border
        cell.fill = fill_peach

    items3 = [
        "E-Waste scrap mixed", "Adaptor / Charger", "Aluminium scraps", "Al. Castiron", "Aluminium and mild mixed",
        "Cable mixed", "Choke scraps", "Compressor", "Copper scraps", "Electrical item", "Chair office used",
        "Hard disk", "Lighting Equipment", "Lens", "Mild steel", "Mixed material", "Motor -", "Plastic scraps",
        "Plastic abs", "Plastic box", "Radiotor", "Steel", "SMPS", "PCB scraps", "Transformer"
    ]
    for idx, item in enumerate(items3, 1):
        r = idx + 6
        ws3.cell(row=r, column=1, value=idx).alignment = align_center
        ws3.cell(row=r, column=2, value=item).alignment = align_left
        ws3.cell(row=r, column=3, value=0.0).number_format = "0.000"
        ws3.cell(row=r, column=8, value=0.0).number_format = "0.000"
        ws3.cell(row=r, column=9, value=0.0).number_format = "0.00"
        amt_cell = ws3.cell(row=r, column=10, value=f"=H{r}*I{r}")
        amt_cell.number_format = "0.000"
        amt_cell.font = red_font

        for c in range(1, 11):
            ws3.cell(row=r, column=c).border = thin_border

    tot_row3 = len(items3) + 7
    ws3.cell(row=tot_row3, column=2, value="Total").font = bold_font
    ws3.cell(row=tot_row3, column=3, value=f"=SUM(C7:C{tot_row3-1})").font = bold_font
    ws3.cell(row=tot_row3, column=4, value=f"=SUM(D7:D{tot_row3-1})").font = bold_font
    ws3.cell(row=tot_row3, column=5, value=f"=SUM(E7:E{tot_row3-1})").font = bold_font
    ws3.cell(row=tot_row3, column=6, value=f"=SUM(F7:F{tot_row3-1})").font = bold_font
    ws3.cell(row=tot_row3, column=7, value=f"=SUM(G7:G{tot_row3-1})").font = bold_font
    ws3.cell(row=tot_row3, column=8, value=f"=SUM(H7:H{tot_row3-1})").font = bold_font
    ws3.cell(row=tot_row3, column=10, value=f"=SUM(J7:J{tot_row3-1})").font = bold_red_font
    for c in range(1, 11):
        cell = ws3.cell(row=tot_row3, column=c)
        cell.border = thin_border
        cell.fill = fill_amber

    # ── 4. IncomingMaterial Sheet ─────────────────────────────────────────────
    ws4 = wb.create_sheet(title="IncomingMaterial")
    ws4.merge_cells("A1:H1")
    ws4["A1"] = "Right Ewaste Recycle Private Limited,"
    ws4["A1"].font = title_font
    ws4["A1"].alignment = align_center
    ws4["A1"].fill = fill_gold

    ws4.merge_cells("A2:H2")
    ws4["A2"] = "Factory Daily Report"
    ws4["A2"].font = subtitle_font
    ws4["A2"].alignment = align_center
    ws4["A2"].fill = fill_gold

    ws4.merge_cells("A3:C3")
    ws4["A3"] = "Date :31.03.2023"
    ws4["A3"].font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    ws4["A3"].fill = fill_grey

    ws4.merge_cells("D3:H3")
    ws4["D3"] = "Branch: Mumbai."
    ws4["D3"].font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    ws4["D3"].alignment = align_right
    ws4["D3"].fill = fill_grey

    ws4.merge_cells("A5:H5")
    ws4["A5"] = "Incoming Material Details"
    ws4["A5"].font = bold_font
    ws4["A5"].alignment = align_center
    ws4["A5"].fill = fill_cyan

    headers4 = ["Sl .No.", "IGP no.", "Procurement Inv. No", "Company/Individual", "Nomenclature", "Qty(No.)", "Weight(Kgs)", "Total Wt (Kgs)"]
    for col_idx, h in enumerate(headers4, 1):
        cell = ws4.cell(row=6, column=col_idx, value=h)
        cell.font = bold_font
        cell.alignment = align_center
        cell.border = thin_border
        cell.fill = fill_peach

    for r in range(7, 27):
        for c in range(1, 9):
            cell = ws4.cell(row=r, column=c)
            cell.border = thin_border

    ws4.cell(row=27, column=5, value="Total").font = bold_font
    ws4.cell(row=27, column=6, value="=SUM(F7:F26)").font = bold_font
    ws4.cell(row=27, column=7, value="=SUM(G7:G26)").font = bold_font
    ws4.cell(row=27, column=8, value="=SUM(H7:H26)").font = bold_font
    for c in range(1, 9):
        cell = ws4.cell(row=27, column=c)
        cell.border = thin_border
        cell.fill = fill_yellow

    # ── 5. OutgoingMaterial Sheet ─────────────────────────────────────────────
    ws5 = wb.create_sheet(title="OutgoingMaterial")
    ws5.merge_cells("A1:H1")
    ws5["A1"] = "Right Ewaste Recycle Private Limited,"
    ws5["A1"].font = title_font
    ws5["A1"].alignment = align_center
    ws5["A1"].fill = fill_gold

    ws5.merge_cells("A2:H2")
    ws5["A2"] = "Factory Daily Report"
    ws5["A2"].font = subtitle_font
    ws5["A2"].alignment = align_center
    ws5["A2"].fill = fill_gold

    ws5.merge_cells("A3:C3")
    ws5["A3"] = "Date :31.03.2023"
    ws5["A3"].font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    ws5["A3"].fill = fill_grey

    ws5.merge_cells("D3:H3")
    ws5["D3"] = "Branch: Mumbai."
    ws5["D3"].font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    ws5["D3"].alignment = align_right
    ws5["D3"].fill = fill_grey

    ws5.merge_cells("A5:H5")
    ws5["A5"] = "Outgoing Material Details"
    ws5["A5"].font = bold_font
    ws5["A5"].alignment = align_center
    ws5["A5"].fill = fill_cyan

    headers5 = ["Sl .No.", "Dispatch No.", "Sales Inv. No", "Buyer Company/Individual", "Nomenclature", "Qty(No.)", "Weight(Kgs)", "Total Wt (Kgs)"]
    for col_idx, h in enumerate(headers5, 1):
        cell = ws5.cell(row=6, column=col_idx, value=h)
        cell.font = bold_font
        cell.alignment = align_center
        cell.border = thin_border
        cell.fill = fill_peach

    for r in range(7, 27):
        for c in range(1, 9):
            cell = ws5.cell(row=r, column=c)
            cell.border = thin_border

    ws5.cell(row=27, column=5, value="Total").font = bold_font
    ws5.cell(row=27, column=6, value="=SUM(F7:F26)").font = bold_font
    ws5.cell(row=27, column=7, value="=SUM(G7:G26)").font = bold_font
    ws5.cell(row=27, column=8, value="=SUM(H7:H26)").font = bold_font
    for c in range(1, 9):
        cell = ws5.cell(row=27, column=c)
        cell.border = thin_border
        cell.fill = fill_yellow

    wb.save(TEMPLATE_PATH)
    print(f"Master template successfully updated at: {TEMPLATE_PATH}")


if __name__ == "__main__":
    create_factory_report_master_template()
