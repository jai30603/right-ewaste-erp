# Purchase Module V2 – Software Requirement Specification (SRS)

## Version: 2.0
**Module**: Purchase Management  
**Status**: Approved & Implemented  
**Prepared By**: Software Architecture Team  

---

## Chapter 1 – Introduction
### 1.1 Purpose
The Purchase Module is responsible for recording every incoming e-waste transaction received by Right Ewaste Recycle Pvt. Ltd. Unlike a traditional ERP, this module is not just for supplier purchases. It represents the entry point of all incoming materials, regardless of how they are received (Donation, AMC, Government Collections, or direct pickups). The Purchase Module is the foundation for inventory, factory processing, refurbishment, segregation, material tracking, recycling certificates, and dashboard reporting.

### 1.2 Objective
The objective of Purchase Module V2 is to transform the existing Purchase Invoice functionality into a complete Inbound Material Management System while preserving all existing working features. It manages:
*   Incoming material streams and intake modes.
*   Verification checks on quantities, weights, and items.
*   State-split GST calculations.
*   Automatic real-time stock additions.

---

## Chapter 2 – Business Workflow & Operational Flow
### 2.1 Purpose
The Purchase Module represents the complete intake process for all incoming e-waste and recyclable materials. Downstream operations like factory segregation, recycling processes, and certificate generation depend directly on this data.

### 2.2 Business Workflow
1.  **Material Arrives**: E-waste is unloaded at the collection point.
2.  **Weight & Quantity Verification**: Weight or pieces are verified.
3.  **Intake Entry**: The operator records the transaction specifying the Intake Type (Purchase, Donation, Gov Collection, AMC, Pickup) and party.
4.  **Verification & Confirmation**: Upon confirmation, inventory stock increments automatically.
5.  **Factory Processing Queue / Certificate Generation**: Materials proceed downstream.

---

## Chapter 3 – Functional Requirements
### 3.1 Module Objective
Provide an operational screen and analytics dashboard to manage inbound materials without duplicate entry.

### 3.2 Navigation Structure
*   **Purchase Dashboard**: Real-time KPI statistics and chart graphics.
*   **Purchase Invoice**: Register of transactions, drafts, and confirmations.
*   **Purchase Register**: Excel exportable tabular reports showing taxable value and GST distributions.
*   **Source Party Ledger**: Delivers trace views on specific supplier shipments.

---

## Chapter 4 – Business Rules & Business Logic
### 4.1 Purchase Philosophy
Once confirmed, ownership is transfered, inventory increases, and metrics feed the dashboard immediately. 

### 4.2 Numbering Convention
*   Invoice numbers are auto-generated on creation as `PUR-YYYY-XXXXXX` (e.g. `PUR-2026-000001`).

### 4.3 Validation Rules
*   Source Party, Date, and at least one Item are mandatory.
*   Item weights/pieces must follow the material tracking rules (`WEIGHT_ONLY`, `PIECES_ONLY`, or `BOTH`).
*   Intra-state purchases (supplier state matches company state) receive CGST + SGST. Inter-state purchases receive IGST.

---

## Chapter 5 – Technical Architecture & Implementation Specification
*   **Layered Architecture**: Flask Routes (Blueprint) → Service Layer → Repository Layer → SQLite Database.
*   **Folder Structure**:
    *   `backend/routes/purchase.py`
    *   `backend/repositories/purchase_repository.py`
    *   `backend/services/purchase_service.py`
    *   `backend/templates/purchase/`

---

## Chapter 6 – Future Compatibility, Roadmap & Version History
### 6.1 Module Vision
The Purchase Module should become the official entry point for every material entering Right Ewaste. It serves as the starting point of the entire material lifecycle.

### 6.2 Position inside the ERP
```
Masters ── Companies, Parties, Materials
 ↓
Purchase ── Dashboard, Invoices, Register, Ledgers
 ↓
Inventory ── Current Stock, Material Ledgers
 ↓
Processing / Factory ── Segregation, Refurbishment, Batches
 ↓
Certificates ── Recycling Certificates
 ↓
Sales ── Outbound Invoices
```

### 6.3 Certificate Compatibility
The Purchase Module does not generate certificates itself but captures all needed data (Source Party, Purchase number/date, weights, pieces, vehicle and reference numbers, remarks).

### 6.4 Certificate Architecture & Processing Batch Integration
*   **Processing Batch Primary Reference**: Certificates shall link to **Processing Batches** rather than directly to Purchases. This supports:
    *   *Multiple Purchases → One Batch*: Combining materials from different collections into one processing run.
    *   *One Purchase → Multiple Batches*: Splitting a single shipment into different runs (e.g. refurbishing some and dismantling the rest).
*   **Traceability**: Complete traceability from Certificate → Processing Batch → Purchase → Source Party is preserved.

### 6.5 Version Roadmap
*   **Version 1 (Completed)**: Purchase CRUD, GST, PDF export.
*   **Version 2 (Current)**: Inbound Register, Dashboard, Party Ledger, Intake Types, dynamic field disabling.
*   **Version 3**: Factory Queue, Material Inspection, Batch Tracking, Warehouse locations.
*   **Version 4**: Certificate Module integration, email sending, asset uploads.
*   **Version 5**: Accounting voucher entry, cash & bank modules.
