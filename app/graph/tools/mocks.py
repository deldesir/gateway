from typing import Optional
from langchain_core.tools import tool

@tool
def check_stock(item_name: str) -> str:
    """
    Check if an item is in stock at the Hardware Store.
    
    Args:
        item_name (str): The name of the item (e.g., 'Cement', 'Hammer').
    """
    # Mock inventory
    inventory = {
        "cement": "500 bags available. Price: 850 HTG.",
        "rebar": "1000 units (1/2 inch) available.",
        "paint": "White and Blue in stock. Red is out of stock.",
    }
    
    key = item_name.lower()
    for k, v in inventory.items():
        if k in key:
            return v
            
    return f"Status for '{item_name}': In stock (General inventory)."

@tool
def order_delivery(item_name: str, address: str, phone: str) -> str:
    """
    Schedule a delivery for hardware supplies.
    
    Args:
        item_name (str): Items to deliver.
        address (str): Delivery address.
        phone (str): Contact number.
    """
    return f"Delivery confirmed for '{item_name}' to {address}. Driver will call {phone}."

@tool
def schedule_viewing(property_id: str, date: str) -> str:
    """
    Schedule a request to view a real estate property.
    
    Args:
        property_id (str): The ID of the property (e.g., 'APT-101').
        date (str): Preferred date/time.
    """
    return f"Viewing request received for {property_id} on {date}. An agent will confirm shortly."
