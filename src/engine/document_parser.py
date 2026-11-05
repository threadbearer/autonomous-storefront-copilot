"""Paper purchase order and delivery invoice parser for supplier receiving."""

from datetime import date
import json
from typing import Any, Dict, List, Optional
from src.models.inventory import PaperPurchaseOrder, POLineItem


class PurchaseOrderParser:
    """Parses digitized paper purchase orders/invoices from commercial retail distributors into structured data."""

    DISTRIBUTOR_TEMPLATES = {
        "APEX": "Apex National Distribution Partners",
        "METRO": "Metro Wholesale Logistics",
        "COREMARK": "Core-Mark Retail Distribution",
        "SYSCO": "Sysco Commercial Goods",
        # Backward compatibility aliases
        "SGWS": "Southern Glazer's Wine & Spirits",
        "RNDC": "Republic National Distributing Company",
        "BREAKTHRU": "Breakthru Beverage Group",
        "REYES": "Reyes Beer Division",
    }

    @classmethod
    def parse_extracted_payload(cls, raw_data: Dict[str, Any]) -> PaperPurchaseOrder:
        """Converts raw OCR/VLM extracted JSON into a validated PaperPurchaseOrder object."""
        distributor = raw_data.get("distributor_name", "Apex National Distribution Partners")
        inv_num = raw_data.get("invoice_number", f"INV-{date.today().strftime('%Y%m%d')}-001")
        inv_date = raw_data.get("invoice_date", date.today().isoformat())
        confidence = float(raw_data.get("ocr_confidence", 0.95))

        line_items: List[POLineItem] = []
        for item in raw_data.get("line_items", []):
            cost = float(item.get("unit_cost", item.get("bottle_cost", 0.0)))
            line_items.append(
                POLineItem(
                    sku_id=item["sku_id"],
                    upc=item.get("upc", ""),
                    description=item.get("description", ""),
                    pack_size=int(item.get("pack_size", 12)),
                    cases_invoiced=int(item.get("cases_invoiced", 1)),
                    unit_cost=cost,
                    case_cost=float(item.get("case_cost", 0.0)),
                    cases_received=item.get("cases_received"),
                    bottle_cost=cost,
                )
            )

        return PaperPurchaseOrder(
            distributor_name=distributor,
            invoice_number=inv_num,
            invoice_date=inv_date,
            line_items=line_items,
            raw_ocr_confidence=confidence,
            verified_by_clerk=False,
        )

    @classmethod
    def create_mock_delivery_invoice(
        cls, distributor_code: str = "APEX"
    ) -> PaperPurchaseOrder:
        """Generates a realistic sample weekly delivery invoice for testing."""
        distributor_name = cls.DISTRIBUTOR_TEMPLATES.get(
            distributor_code, "Apex National Distribution Partners"
        )
        sample_payload = {
            "distributor_name": distributor_name,
            "invoice_number": f"APX-{date.today().strftime('%m%d')}-8842",
            "invoice_date": date.today().isoformat(),
            "ocr_confidence": 0.98,
            "line_items": [
                {
                    "sku_id": "SKU-ENERGY-16OZ",
                    "upc": "088004144694",
                    "description": "Vitality Energy Drink 16oz (12pk)",
                    "pack_size": 12,
                    "cases_invoiced": 4,
                    "unit_cost": 1.80,
                    "case_cost": 21.60,
                },
                {
                    "sku_id": "SKU-USB-CHARGER",
                    "upc": "858000005018",
                    "description": "Braided 65W Fast Charger Kit",
                    "pack_size": 6,
                    "cases_invoiced": 2,
                    "unit_cost": 14.00,
                    "case_cost": 84.00,
                },
                {
                    "sku_id": "SKU-BT-EARBUDS",
                    "upc": "088110551025",
                    "description": "Pro Wireless Bluetooth Earbuds",
                    "pack_size": 10,
                    "cases_invoiced": 2,
                    "unit_cost": 25.00,
                    "case_cost": 250.00,
                },
                {
                    "sku_id": "SKU-PROTEIN-BARS",
                    "upc": "088004000303",
                    "description": "Artisan Protein Bars 10-Pack",
                    "pack_size": 24,
                    "cases_invoiced": 1,
                    "unit_cost": 8.50,
                    "case_cost": 204.00,
                },
            ],
        }
        return cls.parse_extracted_payload(sample_payload)
