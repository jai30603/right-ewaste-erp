"""
Global Search Service
Provides unified helper functions to search across multiple ERP entities:
Party, Material, Purchase, Inventory, and Sales.
"""
from repositories.party_repository import search_parties
from repositories.material_repository import search_materials
from repositories.purchase_repository import get_all_purchase_invoices
from repositories.sales_repository import get_all_invoices
from repositories.inventory_repository import get_stock_summary

class GlobalSearchService:
    """
    Service layer providing global unified entity search helpers.
    """
    
    @classmethod
    def global_search(cls, query):
        """
        Executes search across all core entities using query keywords and bundles them.
        :param query: search keyword (string)
        :return: Dict containing matching rows grouped by category
        """
        if not query or not query.strip():
            return {
                "parties": [],
                "materials": [],
                "purchases": [],
                "sales": [],
                "inventory": []
            }
            
        q = query.strip()
        
        # 1. Search Parties
        parties = search_parties(q)
        
        # 2. Search Materials
        materials = search_materials(q)
        
        # 3. Search Purchase Invoices
        purchases = get_all_purchase_invoices(search_query=q)
        
        # 4. Search Sales Invoices
        sales = get_all_invoices(search_query=q)
        
        # 5. Search Inventory
        inventory = get_stock_summary(search_query=q)
        
        return {
            "parties": [dict(row) for row in parties],
            "materials": [dict(row) for row in materials],
            "purchases": [dict(row) for row in purchases],
            "sales": [dict(row) for row in sales],
            "inventory": [dict(row) for row in inventory]
        }
