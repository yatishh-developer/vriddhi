# Business Sector Feature Flags

Brand: VRIDDHI  
Ecosystem: VABOS - Vriddhi AI Billing Operating System

The admin app selects one `businessSector`. The backend returns `featureFlags` to the staff app, and the staff app hides features that are not enabled or not allowed by staff permissions.

## Sectors

| Sector | Default modules |
| --- | --- |
| `restaurant_cafe` | Billing, KOT, pending KOT, table/token, dine-in/takeaway/parcel, kitchen display, QR menu |
| `retail_kirana` | Billing, barcode, hold bill, customer ledger, inventory, purchase/restock |
| `fashion_garments` | Billing, barcode/SKU, size/color variants, hold bill, exchange/return placeholder |
| `electronics` | Billing, barcode/SKU, serial/IMEI placeholder, warranty placeholder, customer ledger |
| `medical_pharmacy` | Billing, barcode, batch/expiry placeholder, inventory |
| `salon_service` | Service billing, appointment placeholder, staff assignment placeholder |
| `general_business` | Simple billing, products/services, customer ledger, hold bill |

## Flags

```json
{
  "kotEnabled": true,
  "barcodeEnabled": false,
  "holdBillEnabled": false,
  "tableEnabled": true,
  "kitchenEnabled": true,
  "variantsEnabled": false,
  "batchExpiryEnabled": false,
  "serialNumberEnabled": false,
  "serviceModeEnabled": false
}
```

## Get Feature Flags

```http
GET /staff/feature-flags?sector=retail_kirana
```

```json
{
  "businessSector": "retail_kirana",
  "featureFlags": {
    "kotEnabled": false,
    "barcodeEnabled": true,
    "holdBillEnabled": true,
    "customerLedgerEnabled": true,
    "inventoryEnabled": true,
    "purchaseRestockEnabled": true
  }
}
```

Admin can manually override modules after sector selection. Staff UI must use both `featureFlags` and staff `permissions`.
