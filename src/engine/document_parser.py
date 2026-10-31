"""Paper purchase order and delivery invoice parser for supplier receiving."""

from datetime import date
import json
from typing import Any, Dict, List, Optional
from src.models.inventory import PaperPurchaseOrder, POLineItem


class PurchaseOrderParser:
    """Parses digitized paper purchase orders/invoices from liquor distributors into structured data."""

    DISTRIBUTOR_TEMPLATES = {
        "SGWS": "Southern Glazer's Wine & Spirits",
        "RNDC": "Republic National Distributing Company",
        "BREAKTHRU": "Breakthru Beverage Group",
        "REYES": "Reyes Beer Division",
    }

    @classmethod
    def parse_extracted_payload(cls, raw_data: Dict[str, Any]) -> PaperPurchaseOrder:
        """Converts raw OCR/VLM extracted JSON into a validated PaperPurchaseOrder object."""
        distributor = raw_data.get("distributor_name", "Unknown Distributor")
        inv_num = raw_data.get("invoice_number", f"INV-{date.today().strftime('%Y%m%d')}-001")
        inv_date = raw_data.get("invoice_date", date.today().isoformat())
        confidence = float(raw_data.get("ocr_confidence", 0.95))

        line_items: List[POLineItem] = []
        for item in raw_data.get("line_items", []):
            line_items.append(
                POLineItem(
                    sku_id=item["sku_id"],
                    upc=item.get("upc", ""),
                    description=item.get("description", ""),
                    pack_size=int(item.get("pack_size", 12)),
                    cases_invoiced=int(item.get("cases_invoiced", 1)),
                    bottle_cost=float(item.get("bottle_cost", 0.0)),
                    case_cost=float(item.get("case_cost", 0.0)),
                    cases_received=item.get("cases_received"),
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
        cls, distributor_code: str = "SGWS"
    ) -> PaperPurchaseOrder:
        """Generates a realistic sample weekly delivery invoice for testing."""
        distributor_name = cls.DISTRIBUTOR_TEMPLATES.get(
            distributor_code, "Southern Glazer's Wine & Spirits"
        )
        sample_payload = {
            "distributor_name": distributor_name,
            "invoice_number": f"SG-{date.today().strftime('%m%d')}-9401",
            "invoice_date": date.today().isoformat(),
            "ocr_confidence": 0.98,
            "line_items": [
                {
                    "sku_id": "SKU-TITOS-750",
                    "upc": "088004144694",
                    "description": "Tito's Handmade Vodka 750ml",
                    "pack_size": 12,
                    "cases_invoiced": 4,
                    "bottle_cost": 16.25,
                    "case_cost": 195.00,
                },
                {
                    "sku_id": "SKU-CASAMIGOS-BLANCO-750",
                    "upc": "858000005018",
                    "description": "Casamigos Tequila Blanco 750ml",
                    "pack_size": 6,
                    "cases_invoiced": 2,
                    "bottle_cost": 42.00,
                    "case_cost": 252.00,
                },
                {
                    "sku_id": "SKU-HENNESSY-VS-375",
                    "upc": "088110551025",
                    "description": "Hennessy VS Cognac 375ml",
                    "pack_size": 24,
                    "cases_invoiced": 2,
                    "bottle_cost": 18.50,
                    "case_cost": 444.00,
                },
                {
                    "sku_id": "SKU-FIREBALL-50",
                    "upc": "088004000303",
                    "description": "Fireball Cinnamon Whisky 50ml Sleeves",
                    "pack_size": 120,
                    "cases_invoiced": 1,
                    "bottle_cost": 0.85,
                    "case_cost": 102.00,
                },
            ],
        }
        return cls.parse_extracted_payload(sample_payload)
