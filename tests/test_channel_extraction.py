import re

def test_extraction():
    # Target format: "@contact.first_name (@contact.urn > @contact.channel) says: @input"
    # Example: "Bob (whatsapp:50912345678 > 5099999999) says: #help"
    
    inputs = [
        "Bob (whatsapp:50912345678 > 5099999999) says: #help",
        "Alice (tel:+12345 > +98765) says: Hello world",
        "Unknown (509123 > 509999) says: Test",
        "OldFormat (whatsapp:123) says: Old style",
        "NoPrefix: just a message"
    ]
    
    # Current Regex (for reference): r"^.*?\((?:(?:tel|whatsapp|telegram):)?\+?\d+\) says:\s+"
    # We need to capture the > channel part if present.
    
    # Regex Refined:
    # 1. Start lazily: `^.*?`
    # 2. Open Parend: `\(`
    # 3. Capture URN (non-greedy until > or )): `(?P<urn>[^)>]+?)`
    # 4. Optional Channel Group:
    #    - Separator: `\s*>\s*`
    #    - Capture Channel: `(?P<channel>[^)]+)`
    # 5. Close Parend: `\)`
    # 6. Suffix: ` says:\s+`
    
    regex = r"^.*?\((?P<urn>[^)>]+?)(?:\s*>\s*(?P<channel>[^)]+))?\) says:\s+"
    
    print(f"Testing Regex: {regex}\n")
    
    for i, txt in enumerate(inputs):
        print(f"--- Case {i+1}: '{txt}' ---")
        match = re.search(regex, txt)
        if match:
            urn = match.group("urn")
            channel = match.group("channel")
            content = re.sub(regex, "", txt, count=1)
            
            print(f"MATCHED!")
            print(f"  URN: {urn}")
            print(f"  Channel: {channel}")
            print(f"  Content: '{content}'")
            
            if i == 0:
                assert urn == "whatsapp:50912345678"
                assert channel == "5099999999"
                assert content == "#help"
            if i == 3:
                assert urn == "whatsapp:123"
                assert channel is None
                assert content == "Old style"
                
        else:
            print("NO MATCH (Normal behavior for NoPrefix)")
            if i < 4:
                print("  FAILED! Should have matched.")

if __name__ == "__main__":
    test_extraction()
