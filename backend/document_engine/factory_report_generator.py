import json
from pathlib import Path
import openpyxl

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = BASE_DIR / "documents" / "templates" / "factory_report" / "factory_report_template.xlsx"
MAPPING_PATH = BASE_DIR / "documents" / "templates" / "factory_report" / "factory_report_mapping.json"


def _match_material_data(template_item_name, material_summary, inventory, disposal_queue_summary=None):
    if not template_item_name:
        return None
    t_norm = str(template_item_name).strip().lower()

    # Check disposal_queue_summary first if present for disposal items
    if disposal_queue_summary:
        for key, data in disposal_queue_summary.items():
            if t_norm == key or t_norm in key or key in t_norm:
                return {
                    "received_qty": data.get("qty", 0),
                    "received_weight": data.get("weight", 0.0),
                    "sold_qty": 0,
                    "sold_weight": data.get("weight", 0.0),
                    "rate": 0.0,
                    "os_qty": 0
                }

    # Direct or substring match in material_summary
    for key, data in material_summary.items():
        if t_norm == key or t_norm in key or key in t_norm:
            return data

    # Direct or substring match in inventory
    for key, data in inventory.items():
        if t_norm == key or t_norm in key or key in t_norm:
            return {
                "received_qty": 0,
                "received_weight": 0.0,
                "sold_qty": 0,
                "sold_weight": 0.0,
                "rate": data.get("rate", 0.0),
                "os_qty": data.get("qty", 0)
            }

    return None


class FactoryReportGenerator:

    def __init__(self, template_path=None, mapping_path=None):
        self.template_path = Path(template_path) if template_path else TEMPLATE_PATH
        self.mapping_path = Path(mapping_path) if mapping_path else MAPPING_PATH
        self._load_mapping()

    def _load_mapping(self):
        with open(self.mapping_path, "r", encoding="utf-8") as f:
            self.mapping_config = json.load(f)

    def generate(self, erp_data, output_path):
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template workbook not found at {self.template_path}")

        # 1. Load Master Template (preserves formulas, styles, merged cells)
        wb = openpyxl.load_workbook(self.template_path)
        mappings = self.mapping_config.get("mappings", {})

        material_summary = erp_data.get("material_summary", {})
        disposal_queue_summary = erp_data.get("disposal_queue_summary", {})
        inventory = erp_data.get("inventory", {})

        # 2. Populate Header Information
        hdr_map = mappings.get("header", {})
        dt_str = erp_data.get("report_date", "")

        for key, info in hdr_map.items():
            sheet_name = info["sheet"]
            cell_ref = info["cell"]
            prefix = info.get("prefix", "")
            if sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                if key == "company_name":
                    ws[cell_ref] = prefix + erp_data.get("company", {}).get("company_name", "Right Ewaste Recycle Private Limited")
                elif key == "branch_location":
                    ws[cell_ref] = prefix + erp_data.get("company", {}).get("branch_location", "Mumbai Branch")
                elif key == "report_date_str":
                    ws[cell_ref] = prefix + dt_str

        # 3. Populate Attendance Summary
        att_map = mappings.get("attendance", {})
        att_data = erp_data.get("attendance", {})
        for key, info in att_map.items():
            sheet_name = info["sheet"]
            cell_ref = info["cell"]
            if sheet_name in wb.sheetnames and key in att_data:
                ws = wb[sheet_name]
                ws[cell_ref] = att_data[key]

        # 4. Populate EwasteMaterials Sheet Data
        if "EwasteMaterials" in wb.sheetnames:
            ws_ew = wb["EwasteMaterials"]
            for r in range(8, 35):
                item_name = ws_ew.cell(row=r, column=2).value
                matched = _match_material_data(item_name, material_summary, inventory)
                if matched:
                    recv_qty = matched.get("received_qty", 0)
                    recv_wt = matched.get("received_weight", 0.0)
                    sold_qty = matched.get("sold_qty", 0)
                    sold_wt = matched.get("sold_weight", 0.0)
                    os_qty = matched.get("os_qty", 0)
                    rate = matched.get("rate", 0.0)

                    cs_qty = max(0, os_qty + recv_qty - sold_qty)
                    cs_wt = max(0.0, recv_wt - sold_wt)

                    if recv_qty > 0 or recv_wt > 0 or os_qty > 0 or rate > 0:
                        ws_ew.cell(row=r, column=3, value=os_qty)
                        ws_ew.cell(row=r, column=4, value=0.0)
                        ws_ew.cell(row=r, column=5, value=recv_qty if recv_qty > 0 else None)
                        ws_ew.cell(row=r, column=6, value=recv_wt if recv_wt > 0 else None)
                        ws_ew.cell(row=r, column=11, value=cs_qty)
                        ws_ew.cell(row=r, column=12, value=cs_wt)
                        if rate > 0:
                            ws_ew.cell(row=r, column=13, value=rate)

        # 5. Populate Disposal Sheet Data
        if "Disposal" in wb.sheetnames:
            ws_disp = wb["Disposal"]
            for r in range(7, 22):
                item_name = ws_disp.cell(row=r, column=2).value
                matched = _match_material_data(item_name, material_summary, inventory, disposal_queue_summary=disposal_queue_summary)
                if matched:
                    recv_wt = matched.get("received_weight", 0.0)
                    sold_wt = matched.get("sold_weight", 0.0)
                    rate = matched.get("rate", 0.0)
                    cs_wt = max(0.0, recv_wt - sold_wt)

                    if recv_wt > 0 or sold_wt > 0 or rate > 0:
                        ws_disp.cell(row=r, column=4, value=recv_wt if recv_wt > 0 else None)
                        ws_disp.cell(row=r, column=7, value=sold_wt if sold_wt > 0 else None)
                        ws_disp.cell(row=r, column=8, value=cs_wt)
                        if rate > 0:
                            ws_disp.cell(row=r, column=9, value=rate)

        # 6. Populate ScrapMaterials Sheet Data
        if "ScrapMaterials" in wb.sheetnames:
            ws_scrap = wb["ScrapMaterials"]
            for r in range(7, 32):
                item_name = ws_scrap.cell(row=r, column=2).value
                matched = _match_material_data(item_name, material_summary, inventory)
                if matched:
                    recv_wt = matched.get("received_weight", 0.0)
                    sold_wt = matched.get("sold_weight", 0.0)
                    rate = matched.get("rate", 0.0)
                    cs_wt = max(0.0, recv_wt - sold_wt)

                    if recv_wt > 0 or sold_wt > 0 or rate > 0:
                        ws_scrap.cell(row=r, column=4, value=recv_wt if recv_wt > 0 else None)
                        ws_scrap.cell(row=r, column=7, value=sold_wt if sold_wt > 0 else None)
                        ws_scrap.cell(row=r, column=8, value=cs_wt)
                        if rate > 0:
                            ws_scrap.cell(row=r, column=9, value=rate)

        # 7. Populate Incoming Materials Rows
        inc_map = mappings.get("incoming_materials", {})
        inc_sheet_name = inc_map.get("sheet", "IncomingMaterial")
        inc_data = erp_data.get("incoming_materials", [])
        if inc_sheet_name in wb.sheetnames and inc_data:
            ws_inc = wb[inc_sheet_name]
            start_r = inc_map.get("start_row", 7)
            cols = inc_map.get("columns", {})

            for idx, item in enumerate(inc_data):
                curr_r = start_r + idx
                if curr_r >= 27:
                    break
                ws_inc[f"{cols['sno']}{curr_r}"] = item.get("sno", idx + 1)
                ws_inc[f"{cols['igp_no']}{curr_r}"] = item.get("igp_no", "")
                ws_inc[f"{cols['procurement_inv']}{curr_r}"] = item.get("procurement_inv", "")
                ws_inc[f"{cols['supplier_name']}{curr_r}"] = item.get("supplier_name", "")
                ws_inc[f"{cols['nomenclature']}{curr_r}"] = item.get("nomenclature", "")
                ws_inc[f"{cols['qty']}{curr_r}"] = item.get("qty", 0)
                ws_inc[f"{cols['weight']}{curr_r}"] = item.get("weight", 0.0)
                ws_inc[f"{cols['total_weight']}{curr_r}"] = item.get("total_weight", 0.0)

        # 8. Populate Outgoing Materials Rows
        out_map = mappings.get("outgoing_materials", {})
        out_sheet_name = out_map.get("sheet", "OutgoingMaterial")
        out_data = erp_data.get("outgoing_materials", [])
        if out_sheet_name in wb.sheetnames and out_data:
            ws_out = wb[out_sheet_name]
            start_r = out_map.get("start_row", 7)
            cols = out_map.get("columns", {})

            for idx, item in enumerate(out_data):
                curr_r = start_r + idx
                if curr_r >= 27:
                    break
                ws_out[f"{cols['sno']}{curr_r}"] = item.get("sno", idx + 1)
                ws_out[f"{cols['dispatch_no']}{curr_r}"] = item.get("dispatch_no", "")
                ws_out[f"{cols['sales_inv']}{curr_r}"] = item.get("sales_inv", "")
                ws_out[f"{cols['buyer_name']}{curr_r}"] = item.get("buyer_name", "")
                ws_out[f"{cols['nomenclature']}{curr_r}"] = item.get("nomenclature", "")
                ws_out[f"{cols['qty']}{curr_r}"] = item.get("qty", 0)
                ws_out[f"{cols['weight']}{curr_r}"] = item.get("weight", 0.0)
                ws_out[f"{cols['total_weight']}{curr_r}"] = item.get("total_weight", 0.0)

        # 9. Save populated workbook (preserves formulas & master template styles)
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(out_path)
        return out_path
