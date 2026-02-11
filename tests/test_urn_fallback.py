import re

def extract_urn(message):
    match = re.search(r"(tel|whatsapp|telegram):(\+?\d+)", message)
    if match:
        return f"{match.group(1)}:{match.group(2)}"
    return None

def test_extraction():
    test_cases = [
        ("deldesir (whatsapp:50942614949) says: Konex", "whatsapp:50942614949"),
        ("Hello @contact.urn tel:+12345", "tel:+12345"),
        ("My number is telegram:987654", "telegram:987654"),
        ("No number here", None)
    ]
    
    for msg, expected in test_cases:
        result = extract_urn(msg)
        print(f"Input: '{msg}' -> Extracted: {result}")
        if result != expected:
            print(f"FAILED: Expected {expected}, got {result}")
            exit(1)
            
    print("ALL EXTRACTION TESTS PASSED")

def test_cleaning():
    # Logic from routes.py 
    # Match: "Name (509...) says:" OR "Name (whatsapp:509...) says:"
    prefix_pattern = r"^.*?\((?:(?:tel|whatsapp|telegram):)?\+?\d+\) says:\s+"
    
    test_cases = [
        ("Bob (whatsapp:50912345678) says: #help", "#help"),
        ("Bob (50912345678) says: #user info", "#user info"),
        ("No prefix here", "No prefix here"),
        ("Alice (+1234) says: Hello", "Hello")
    ]
    
    for msg, expected in test_cases:
        clean_content = msg
        if re.search(prefix_pattern, msg):
            clean_content = re.sub(prefix_pattern, "", msg, count=1)
            
        print(f"Input: '{msg}' -> Cleaned: '{clean_content}'")
        if clean_content != expected:
            print(f"FAILED CLEANING: Expected '{expected}', got '{clean_content}'")
            exit(1)

    print("ALL CLEANING TESTS PASSED")

if __name__ == "__main__":
    test_extraction()
    test_cleaning()
